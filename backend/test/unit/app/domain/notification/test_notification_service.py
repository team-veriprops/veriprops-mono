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


def _service(email_ok=True, sms_ok=True):
    svc = object.__new__(NotificationService)
    svc._notification_repo = MagicMock()
    svc._notification_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="n-1"))
    svc._preferences = MagicMock()
    svc._preferences.channels_enabled = AsyncMock(return_value=(email_ok, sms_ok))
    svc._dispatcher = MagicMock()
    svc._dispatcher.dispatch = AsyncMock()
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
