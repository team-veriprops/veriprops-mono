"""Unit tests for BroadcastService (S55)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.broadcast.models import (
    BroadcastAudience,
    BroadcastStatus,
    CreateBroadcastDto,
    ScheduleBroadcastDto,
    UpdateBroadcastDto,
)
from main.app.domain.broadcast.service import BroadcastService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)


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


def _make_broadcast(status="DRAFT", audience="ALL"):
    row = MagicMock()
    row.id = "bc-001"
    row.subject = "Test Subject"
    row.body_text = "Test body"
    row.body_html = None
    row.audience = audience
    row.channels = None
    row.status = status
    row.scheduled_at = None
    row.sent_at = None
    row.created_by = "admin-1"
    row.total_recipients = None
    row.sent_count = 0
    row.date_created = MagicMock()
    row.date_updated = None
    return row


def _make_svc():
    svc = BroadcastService.__new__(BroadcastService)
    repo = MagicMock()
    svc._repo = repo
    return svc, repo


class TestCreateBroadcast:
    async def test_creates_draft_by_default(self):
        svc, repo = _make_svc()
        row = _make_broadcast("DRAFT")
        repo.create_return_model = AsyncMock(return_value=row)

        dto = CreateBroadcastDto(subject="Hello", body_text="World", audience=BroadcastAudience.ALL)
        result = await svc.create(dto, "admin-1")

        assert result.status == BroadcastStatus.DRAFT


class TestScheduleBroadcast:
    async def test_schedules_draft_broadcast(self):
        svc, repo = _make_svc()
        row = _make_broadcast("DRAFT")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
        scheduled_row = _make_broadcast("SCHEDULED")
        scheduled_row.scheduled_at = future
        repo.get_model = AsyncMock(side_effect=[row, scheduled_row])
        repo.update = AsyncMock()

        result = await svc.schedule("bc-001", ScheduleBroadcastDto(scheduled_at=future), "admin-1")

        repo.update.assert_awaited_once()
        assert result.status == BroadcastStatus.SCHEDULED

    async def test_raises_when_not_draft(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=_make_broadcast("SENT"))

        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        with pytest.raises(InvalidResourceStateException):
            await svc.schedule("bc-001", ScheduleBroadcastDto(scheduled_at=future), "admin-1")

    async def test_raises_when_scheduled_at_in_past(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=_make_broadcast("DRAFT"))

        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        with pytest.raises(ValidationException):
            await svc.schedule("bc-001", ScheduleBroadcastDto(scheduled_at=past), "admin-1")


class TestCancelBroadcast:
    async def test_cancels_draft(self):
        svc, repo = _make_svc()
        row = _make_broadcast("DRAFT")
        cancelled = _make_broadcast("CANCELLED")
        repo.get_model = AsyncMock(side_effect=[row, cancelled])
        repo.update = AsyncMock()

        result = await svc.cancel("bc-001", "admin-1")
        assert result.status == BroadcastStatus.CANCELLED

    async def test_cancels_scheduled(self):
        svc, repo = _make_svc()
        row = _make_broadcast("SCHEDULED")
        cancelled = _make_broadcast("CANCELLED")
        repo.get_model = AsyncMock(side_effect=[row, cancelled])
        repo.update = AsyncMock()

        result = await svc.cancel("bc-001", "admin-1")
        assert result.status == BroadcastStatus.CANCELLED

    async def test_raises_when_already_sent(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=_make_broadcast("SENT"))

        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("bc-001", "admin-1")

    async def test_raises_when_not_found(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.cancel("nonexistent", "admin-1")


class TestSendNowBroadcast:
    async def test_transitions_to_sent(self):
        svc, repo = _make_svc()
        row = _make_broadcast("DRAFT")
        sent_row = _make_broadcast("SENT")
        sent_row.sent_count = 0
        sent_row.total_recipients = 0
        repo.get_model = AsyncMock(side_effect=[row, sent_row])
        repo.update = AsyncMock()

        with patch.object(svc, "_resolve_recipients", AsyncMock(return_value=[])):
            result = await svc.send_now("bc-001", "admin-1")

        assert result.status == BroadcastStatus.SENT
