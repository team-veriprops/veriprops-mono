"""NotificationPreferenceService (§12.4) — per-user, per-event opt-out overrides.
Platform default is (email on, sms on) until a row records an override. Repo mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.events.events import EventType
from main.app.domain.notification_preference.models import SetPreferenceDto
from main.app.domain.notification_preference.service import NotificationPreferenceService
from main.appodus_utils.db.session import db_session_ctx


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


def _service():
    svc = object.__new__(NotificationPreferenceService)
    svc._preference_repo = MagicMock()
    svc._preference_repo._session = MagicMock()
    return svc


class TestChannelsEnabled:
    async def test_defaults_to_both_on_when_no_override(self):
        svc = _service()
        svc._preference_repo.get_one = AsyncMock(return_value=None)

        assert await svc.channels_enabled("u-1", EventType.STATUS_CHANGED.value) == (True, True)

    async def test_reflects_recorded_override(self):
        svc = _service()
        svc._preference_repo.get_one = AsyncMock(
            return_value=SimpleNamespace(email_enabled=False, sms_enabled=True)
        )

        assert await svc.channels_enabled("u-1", EventType.STATUS_CHANGED.value) == (False, True)


class TestSet:
    async def test_set_creates_when_absent(self):
        svc = _service()
        svc._preference_repo.get_one = AsyncMock(return_value=None)
        svc._preference_repo.create_return_model = AsyncMock(
            return_value=SimpleNamespace(
                event_type=EventType.STATUS_CHANGED.value, email_enabled=False, sms_enabled=True
            )
        )

        dto = SetPreferenceDto(
            event_type=EventType.STATUS_CHANGED.value, email_enabled=False, sms_enabled=True
        )
        result = await svc.set("u-1", dto)

        assert (result.email_enabled, result.sms_enabled) == (False, True)
        create_dto = svc._preference_repo.create_return_model.call_args.args[0]
        assert create_dto.user_id == "u-1"

    async def test_set_updates_existing_row_in_place(self):
        svc = _service()
        existing = SimpleNamespace(
            event_type=EventType.STATUS_CHANGED.value, email_enabled=True, sms_enabled=True
        )
        svc._preference_repo.get_one = AsyncMock(return_value=existing)
        svc._preference_repo.create_return_model = AsyncMock()

        dto = SetPreferenceDto(
            event_type=EventType.STATUS_CHANGED.value, email_enabled=False, sms_enabled=False
        )
        result = await svc.set("u-1", dto)

        # existing row mutated + re-added; no new row created.
        assert (existing.email_enabled, existing.sms_enabled) == (False, False)
        assert (result.email_enabled, result.sms_enabled) == (False, False)
        svc._preference_repo.create_return_model.assert_not_called()
        svc._preference_repo._session.add.assert_called_once_with(existing)
