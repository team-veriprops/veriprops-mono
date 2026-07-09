"""Unit tests for paginated Security Activity Log (S6)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.session.models import SecurityEventType
from main.app.domain.user.auth.session.service import SessionService
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


def _event_row(i: int):
    row = MagicMock()
    row.id = f"evt-{i}"
    row.type = SecurityEventType.LOGIN_FAILURE_WARNING.value
    row.description = "Repeated invalid credentials (5/7)"
    row.ip_address = "1.2.3.4"
    row.approx_location = None
    row.device = "Chrome"
    row.occurred_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    return row


def _svc(page_for_user):
    event_repo = MagicMock()
    event_repo.page_for_user = page_for_user
    return SessionService(device_repo=MagicMock(), event_repo=event_repo, reset_repo=MagicMock())


class TestPageSecurityEvents:
    async def test_returns_page_with_items_and_meta(self):
        rows = [_event_row(0), _event_row(1)]
        svc = _svc(AsyncMock(return_value=(rows, 7)))

        page = await svc.page_security_events("user-1", page=0, page_size=2)

        assert page.meta.total == 7
        assert page.meta.page == 0
        assert page.meta.page_size == 2
        assert page.meta.count == 2
        assert len(page.items) == 2
        assert page.items[0].type == SecurityEventType.LOGIN_FAILURE_WARNING.value

    async def test_offset_is_zero_indexed(self):
        page_for_user = AsyncMock(return_value=([], 0))
        svc = _svc(page_for_user)

        await svc.page_security_events("user-1", page=2, page_size=10)

        page_for_user.assert_awaited_once_with("user-1", offset=20, limit=10)
