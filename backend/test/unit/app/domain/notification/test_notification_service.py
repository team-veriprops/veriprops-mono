"""Unit tests for NotificationService (S39)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.notification.models import Notification, NotificationEvent
from main.app.domain.notification.service import NotificationService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


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


def _mock_notification(notif_id="n-1", recipient_id="user-1", event_type=NotificationEvent.PAYMENT_CONFIRMED.value):
    n = MagicMock(spec=Notification)
    n.id = notif_id
    n.recipient_id = recipient_id
    n.event_type = event_type
    n.title = "Payment confirmed"
    n.body = "Your payment was confirmed."
    n.entity_type = None
    n.entity_id = None
    n.read = False
    n.date_created = datetime.now(timezone.utc)
    return n


def _make_svc(notification=None):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=notification or _mock_notification())
    repo.list_for_recipient = AsyncMock(return_value=[])
    repo.get_model = AsyncMock(return_value=notification or _mock_notification())
    repo.mark_read = AsyncMock()

    dispatch_repo = MagicMock()
    dispatch_repo.create = AsyncMock()

    pref_repo = MagicMock()
    pref_repo.list_for_user = AsyncMock(return_value=[])
    pref_repo.get_for_user_and_event = AsyncMock(return_value=None)
    pref_repo.create = AsyncMock()

    svc = NotificationService(repo=repo, dispatch_repo=dispatch_repo, pref_repo=pref_repo)
    return svc, repo, dispatch_repo


class TestEmit:
    async def test_creates_notification_row_for_recipient(self):
        notif = _mock_notification(recipient_id="customer-1")
        svc, repo, _ = _make_svc(notification=notif)

        result = await svc.emit(
            NotificationEvent.PAYMENT_CONFIRMED,
            recipient_id="customer-1",
            context={},
        )

        repo.create.assert_called_once()
        call_dto = repo.create.call_args[0][0]
        assert call_dto.recipient_id == "customer-1"
        assert call_dto.event_type == NotificationEvent.PAYMENT_CONFIRMED.value

    async def test_emit_returns_notification_dto(self):
        svc, _, _ = _make_svc()
        result = await svc.emit(
            NotificationEvent.REPORT_READY,
            recipient_id="user-1",
            context={},
            entity_type="Verification",
            entity_id="ver-1",
        )
        assert result.recipient_id == "user-1"

    async def test_emit_with_entity_stores_entity_info(self):
        svc, repo, _ = _make_svc()
        await svc.emit(
            NotificationEvent.NEW_MESSAGE,
            recipient_id="user-1",
            context={},
            entity_type="Thread",
            entity_id="thread-1",
        )
        call_dto = repo.create.call_args[0][0]
        assert call_dto.entity_type == "Thread"
        assert call_dto.entity_id == "thread-1"


class TestMarkRead:
    async def test_mark_read_calls_repo(self):
        notif = _mock_notification(notif_id="n-1", recipient_id="user-1")
        svc, repo, _ = _make_svc(notification=notif)

        await svc.mark_read("n-1", "user-1")

        repo.mark_read.assert_called_once_with("n-1")

    async def test_mark_read_raises_if_wrong_recipient(self):
        notif = _mock_notification(notif_id="n-1", recipient_id="owner-1")
        svc, _, _ = _make_svc(notification=notif)

        with pytest.raises(ResourceNotFoundException):
            await svc.mark_read("n-1", "different-user")


class TestListForRecipient:
    async def test_returns_empty_when_no_notifications(self):
        svc, repo, _ = _make_svc()
        result = await svc.list_for_recipient("user-1")
        assert result == []
        repo.list_for_recipient.assert_called_once_with("user-1", limit=30)
