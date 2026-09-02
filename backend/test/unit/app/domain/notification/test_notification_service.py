"""NotificationService (§12): rule-table fan-out — in-app always, chat-only suppressed,
email/SMS honoured per rule + user opt-out."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.events.events import DomainEvent, EventType
from main.app.domain.notification.rules import rule_for
from main.app.domain.notification.service import NotificationService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.messaging.models import MessageChannel


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _service(email_ok=True, sms_ok=True, milestones=None):
    svc = object.__new__(NotificationService)
    svc._notification_repo = MagicMock()
    svc._notification_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="n-1"))
    svc._preferences = MagicMock()
    svc._preferences.channels_enabled = AsyncMock(return_value=(email_ok, sms_ok))
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch = AsyncMock()
    # The WhatsApp branch resolves its sender lazily from DI so the notification domain
    # never hard-depends on the channel; substituting it here keeps that seam visible.
    svc._milestones = lambda: milestones or MagicMock(
        send_customer_milestone=AsyncMock()
    )
    return svc


def test_rule_table_routes_chat_and_notifications():
    # §12.3: a routine message is Chat-counter only — never a notification.
    assert rule_for(EventType.MESSAGE_SENT).chat_only is True
    assert rule_for(EventType.MESSAGE_SENT).in_app is False
    # Payment confirmed reaches in-app + email + SMS.
    pay = rule_for(EventType.PAYMENT_CONFIRMED)
    assert pay.in_app and pay.email and pay.sms and pay.template is not None


async def test_creates_in_app_and_dispatches_external():
    svc = _service()
    await svc.create_for_event(DomainEvent(
        type=EventType.PAYMENT_CONFIRMED, verification_id="v-1", recipient_user_ids=("cust-1",),
    ))
    svc._notification_repo.create_return_model.assert_awaited_once()
    args, kwargs = svc._dispatcher.dispatch.call_args
    channels = args[2]
    assert MessageChannel.EMAIL in channels and MessageChannel.SMS in channels


async def test_email_opt_out_is_honoured():
    svc = _service(email_ok=False, sms_ok=True)
    await svc.create_for_event(DomainEvent(
        type=EventType.PAYMENT_CONFIRMED, verification_id="v-1", recipient_user_ids=("cust-1",),
    ))
    channels = svc._dispatcher.dispatch.call_args[0][2]
    assert MessageChannel.EMAIL not in channels
    assert MessageChannel.SMS in channels


async def test_chat_only_event_creates_no_notification():
    svc = _service()
    await svc.create_for_event(DomainEvent(
        type=EventType.MESSAGE_SENT, recipient_user_ids=("cust-1",), data={"conversation_id": "c-1"},
    ))
    svc._notification_repo.create_return_model.assert_not_called()
    svc._dispatcher.dispatch.assert_not_called()


async def test_pure_sse_nudge_creates_no_notification():
    svc = _service()
    await svc.create_for_event(DomainEvent(verification_id="v-1", sse_event="task_updated"))
    svc._notification_repo.create_return_model.assert_not_called()


# ─── WhatsApp milestones (§7.6.2, D65/D66; WA-16/WA-34/WA-35) ──────────
#
# The router is where §7.4.6 consent is enforced, so these tests are about the *routing*
# decision — which events reach the WhatsApp branch at all — while the consent and
# recipient gates themselves are pinned in
# test/unit/app/domain/channel/whatsapp/test_milestones.py.


def _milestone_events():
    return (
        EventType.PAYMENT_CONFIRMED,
        EventType.VERIFICATION_STARTED,
        EventType.INSPECTION_COMPLETE,
        EventType.REPORT_READY,
    )


def test_the_four_milestones_declare_a_whatsapp_template():
    """§7.7 names four milestone templates; a `whatsapp=True` row without one would
    dispatch nothing and look like a delivery bug rather than a missing declaration."""
    for event_type in _milestone_events():
        rule = rule_for(event_type)
        assert rule.whatsapp is True, event_type
        assert rule.whatsapp_template is not None, event_type


def test_the_whatsapp_template_is_never_the_email_template():
    """D65: one field cannot be both. The §7.7 Meta template and the email template are
    different artefacts with different bodies and different approval authorities."""
    for event_type in _milestone_events():
        rule = rule_for(event_type)
        if rule.template is not None:
            assert rule.whatsapp_template is not rule.template, event_type


def test_report_ready_always_emails_regardless_of_whatsapp():
    """WA-35, asserted as a property of the table rather than of a code path: the durable
    record of a delivered report cannot depend on a messaging preference."""
    report = rule_for(EventType.REPORT_READY)
    assert report.email is True
    assert report.whatsapp is True


def test_the_two_new_milestones_add_whatsapp_and_nothing_else():
    """D66: no in-app entry and no email. The customer already has a status-change
    notification for the same moment; a second one is noise, not news."""
    for event_type in (EventType.VERIFICATION_STARTED, EventType.INSPECTION_COMPLETE):
        rule = rule_for(event_type)
        assert rule.in_app is False and rule.email is False and rule.sms is False, event_type


def test_no_other_event_reaches_whatsapp():
    """A stray `whatsapp=True` would send a business-initiated template Meta never
    approved for that trigger — the kind of volume that moves a quality rating."""
    from main.app.domain.notification.rules import RULES

    whatsapp_events = {e for e, rule in RULES.items() if rule.whatsapp}
    assert whatsapp_events == set(_milestone_events())


async def test_a_milestone_event_reaches_the_whatsapp_branch():
    milestones = MagicMock(send_customer_milestone=AsyncMock())
    svc = _service(milestones=milestones)
    await svc.create_for_event(DomainEvent(
        type=EventType.REPORT_READY, verification_id="v-1", recipient_user_ids=("cust-1",),
    ))
    milestones.send_customer_milestone.assert_awaited_once()
    args = milestones.send_customer_milestone.await_args.args
    assert args[0] == "cust-1" and args[1] == "v-1"
    assert args[2] is rule_for(EventType.REPORT_READY).whatsapp_template


async def test_a_non_milestone_event_reaches_no_whatsapp_send():
    milestones = MagicMock(send_customer_milestone=AsyncMock())
    svc = _service(milestones=milestones)
    await svc.create_for_event(DomainEvent(
        type=EventType.STATUS_CHANGED, verification_id="v-1",
        recipient_user_ids=("cust-1",), data={"status": "IN_PROGRESS"},
    ))
    milestones.send_customer_milestone.assert_not_called()


async def test_a_whatsapp_only_milestone_creates_no_in_app_row():
    milestones = MagicMock(send_customer_milestone=AsyncMock())
    svc = _service(milestones=milestones)
    await svc.create_for_event(DomainEvent(
        type=EventType.VERIFICATION_STARTED, verification_id="v-1",
        recipient_user_ids=("cust-1",), data={"vid": "VP-2026-0001"},
    ))
    svc._notification_repo.create_return_model.assert_not_called()
    milestones.send_customer_milestone.assert_awaited_once()


async def test_a_failing_milestone_never_breaks_the_fan_out():
    """Same posture as the email branch: the state change already happened, and a
    template hiccup must not roll back the transaction that made it."""
    milestones = MagicMock(
        send_customer_milestone=AsyncMock(side_effect=RuntimeError("Meta is down"))
    )
    svc = _service(milestones=milestones)
    await svc.create_for_event(DomainEvent(
        type=EventType.PAYMENT_CONFIRMED, verification_id="v-1", recipient_user_ids=("cust-1",),
    ))
    svc._notification_repo.create_return_model.assert_awaited_once()
