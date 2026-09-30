"""NotificationPreferenceService (§12.4) — per-user, per-event opt-out overrides.

The platform default is on until a row records an override. What a user may change comes from
the catalogue: the list is theirs alone, each channel carries its mode, and a save outside it
is refused. Repo mocked.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events.events import EventType
from main.app.domain.notification_preference.catalogue import PREFERENCE_COPY, ChannelMode
from main.app.domain.notification_preference.models import SetPreferenceDto
from main.app.domain.notification_preference.service import NotificationPreferenceService
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.appodus_utils.exception.exceptions import ValidationException
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)
from test.utils.repo_fakes import fake_upsert, first_matching

_CUSTOMER = (UserType.USER.value, [UserPersona.CUSTOMER.value])
_AGENT = (UserType.USER.value, [UserPersona.AGENT.value])


def _service(rows=None):
    rows = [] if rows is None else rows
    svc = object.__new__(NotificationPreferenceService)
    svc._preference_repo = MagicMock()
    svc._preference_repo._session = MagicMock()
    svc._preference_repo.list_for_user = AsyncMock(side_effect=lambda user_id: [r for r in rows if r.user_id == user_id])
    svc._preference_repo.get_one = AsyncMock(side_effect=lambda user_id, event_type: first_matching(
        rows, user_id=user_id, event_type=event_type,
    ))
    svc._preference_repo.upsert = fake_upsert(
        lambda values: first_matching(rows, user_id=values["user_id"], event_type=values["event_type"]),
        lambda values: rows.append(SimpleNamespace(deleted=False, **values)) or rows[-1],
    )
    return svc, rows


def _row(event, email=True, sms=True):
    return SimpleNamespace(user_id="u-1", event_type=event.value, email_enabled=email, sms_enabled=sms, deleted=False)


class TestChannelsEnabled:
    async def test_defaults_to_both_on_when_no_override(self):
        svc, _ = _service()

        assert await svc.channels_enabled("u-1", EventType.STATUS_CHANGED.value) == (True, True)

    async def test_reflects_recorded_override(self):
        svc, _ = _service([_row(EventType.STATUS_CHANGED, email=False)])

        assert await svc.channels_enabled("u-1", EventType.STATUS_CHANGED.value) == (False, True)


class TestList:
    async def test_lists_every_event_the_user_can_change_with_the_default_applied(self):
        svc, _ = _service()

        prefs = await svc.list_for_user("u-1", *_CUSTOMER)

        by_event = {p.event_type: p for p in prefs}
        assert EventType.PAYMENT_CONFIRMED in by_event and EventType.NEW_JOB not in by_event
        pay = by_event[EventType.PAYMENT_CONFIRMED]
        assert (pay.label, pay.description) == (PREFERENCE_COPY[EventType.PAYMENT_CONFIRMED].label,
                                                PREFERENCE_COPY[EventType.PAYMENT_CONFIRMED].description)
        assert (pay.email_enabled, pay.sms_enabled) == (True, True)

    async def test_an_override_shows_through(self):
        svc, _ = _service([_row(EventType.PAYMENT_CONFIRMED, email=False)])

        pay = next(p for p in await svc.list_for_user("u-1", *_CUSTOMER) if p.event_type == EventType.PAYMENT_CONFIRMED)

        assert (pay.email_enabled, pay.sms_enabled) == (False, True)

    async def test_each_channel_carries_its_mode(self):
        svc, _ = _service([_row(EventType.REPORT_READY, email=False)])

        report = next(p for p in await svc.list_for_user("u-1", *_CUSTOMER) if p.event_type == EventType.REPORT_READY)

        assert (report.email_mode, report.sms_mode) == (ChannelMode.REQUIRED, ChannelMode.OPTIONAL)
        assert report.email_enabled is True  # required: always sent, whatever a stale row says


class TestSet:
    async def test_records_an_override_for_an_optional_channel(self):
        svc, rows = _service()

        result = await svc.set("u-1", *_CUSTOMER, SetPreferenceDto(
            event_type=EventType.PAYMENT_CONFIRMED, email_enabled=False, sms_enabled=True,
        ))

        assert (result.email_enabled, result.sms_enabled) == (False, True)
        assert [(r.user_id, r.event_type, r.email_enabled) for r in rows] == [("u-1", EventType.PAYMENT_CONFIRMED.value, False)]
        assert svc._preference_repo.upsert.await_args.kwargs == {"unique_index": "uq_notif_prefs_user_event"}

    async def test_updates_the_existing_row_in_place(self):
        existing = _row(EventType.PAYMENT_CONFIRMED)
        svc, rows = _service([existing])

        await svc.set("u-1", *_CUSTOMER, SetPreferenceDto(
            event_type=EventType.PAYMENT_CONFIRMED, email_enabled=False, sms_enabled=False,
        ))

        assert (existing.email_enabled, existing.sms_enabled) == (False, False)
        assert rows == [existing]

    async def test_a_required_or_unused_channel_cannot_be_switched_off(self):
        svc, rows = _service()

        result = await svc.set("u-1", *_CUSTOMER, SetPreferenceDto(
            event_type=EventType.REPORT_READY, email_enabled=False, sms_enabled=False,
        ))

        assert (result.email_enabled, result.sms_enabled) == (True, False)
        assert (rows[0].email_enabled, rows[0].sms_enabled) == (True, False)

    async def test_an_event_not_addressed_to_the_user_is_refused(self):
        svc, rows = _service()

        with pytest.raises(ValidationException):
            await svc.set("u-1", *_AGENT, SetPreferenceDto(
                event_type=EventType.PAYMENT_CONFIRMED, email_enabled=False, sms_enabled=False,
            ))
        assert rows == []

    async def test_an_event_that_cannot_be_changed_is_refused(self):
        svc, rows = _service()

        with pytest.raises(ValidationException):
            await svc.set("u-1", *_CUSTOMER, SetPreferenceDto(
                event_type=EventType.ACCOUNT_SUSPENDED, email_enabled=False, sms_enabled=False,
            ))
        assert rows == []
