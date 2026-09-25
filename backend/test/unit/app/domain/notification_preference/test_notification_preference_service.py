"""NotificationPreferenceService (§12.4) — per-user, per-event opt-out overrides.
Platform default is (email on, sms on) until a row records an override. Repo mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from test.utils.repo_fakes import fake_upsert, first_matching
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
    @staticmethod
    def _with_rows(svc, rows):
        """One statement on the live (user, event) key: concurrent saves can't create twins."""
        svc._preference_repo.upsert = fake_upsert(
            lambda values: first_matching(rows, user_id=values["user_id"], event_type=values["event_type"]),
            lambda values: rows.append(SimpleNamespace(deleted=False, **values)) or rows[-1],
        )

    async def test_set_creates_when_absent(self):
        svc = _service()
        rows = []
        self._with_rows(svc, rows)

        dto = SetPreferenceDto(
            event_type=EventType.STATUS_CHANGED.value, email_enabled=False, sms_enabled=True
        )
        result = await svc.set("u-1", dto)

        assert (result.email_enabled, result.sms_enabled) == (False, True)
        assert [r.user_id for r in rows] == ["u-1"]
        assert svc._preference_repo.upsert.await_args.kwargs == {"unique_index": "uq_notif_prefs_user_event"}

    async def test_set_updates_existing_row_in_place(self):
        svc = _service()
        existing = SimpleNamespace(
            user_id="u-1", event_type=EventType.STATUS_CHANGED.value, email_enabled=True,
            sms_enabled=True, deleted=False,
        )
        rows = [existing]
        self._with_rows(svc, rows)

        dto = SetPreferenceDto(
            event_type=EventType.STATUS_CHANGED.value, email_enabled=False, sms_enabled=False
        )
        result = await svc.set("u-1", dto)

        assert (existing.email_enabled, existing.sms_enabled) == (False, False)
        assert (result.email_enabled, result.sms_enabled) == (False, False)
        assert rows == [existing]  # no second row
