"""Unit tests for ThreadService (S37)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.thread.models import (
    MessageType,
    SenderRole,
    ThreadMessage,
    ThreadType,
)
from main.app.domain.thread.service import ThreadService
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


def _mock_thread(thread_id="t-1", thread_type=ThreadType.CUSTOMER_ADMIN, verification_id="ver-1", task_id=None):
    t = MagicMock()
    t.id = thread_id
    t.thread_type = thread_type.value
    t.verification_id = verification_id
    t.task_id = task_id
    t.date_created = datetime.now(timezone.utc)
    return t


def _mock_message(msg_id="msg-1", sender_role=SenderRole.SYSTEM, body="hello", is_held=False):
    m = MagicMock(spec=ThreadMessage)
    m.id = msg_id
    m.thread_id = "t-1"
    m.sender_id = None
    m.sender_role = sender_role.value
    m.message_type = MessageType.TEXT.value
    m.body = body
    m.attachment_key = None
    m.is_held = is_held
    m.date_created = datetime.now(timezone.utc)
    return m


def _make_svc(thread=None, message=None):
    thread_repo = MagicMock()
    thread_repo.get_model = AsyncMock(return_value=thread)
    thread_repo.list_for_verification = AsyncMock(return_value=[thread] if thread else [])
    thread_repo.get_by_verification_and_type = AsyncMock(return_value=None)
    thread_repo.create_return_model = AsyncMock(return_value=thread)

    msg_repo = MagicMock()
    msg_repo.create_return_model = AsyncMock(return_value=message or _mock_message())
    msg_repo.list_for_thread = AsyncMock(return_value=[])
    msg_repo.get_model = AsyncMock(return_value=message or _mock_message())
    msg_repo.update = AsyncMock()

    svc = ThreadService(thread_repo=thread_repo, message_repo=msg_repo)
    return svc, thread_repo, msg_repo


class TestPostSystemMessage:
    async def test_creates_system_message_row(self):
        thread = _mock_thread()
        svc, _, msg_repo = _make_svc(thread=thread)

        with patch.object(svc, "_publish", AsyncMock()):
            await svc.post_system_message("t-1", "Verification status updated")

        msg_repo.create_return_model.assert_called_once()
        call_arg = msg_repo.create_return_model.call_args[0][0]
        assert call_arg.sender_role == SenderRole.SYSTEM
        assert call_arg.message_type == MessageType.SYSTEM

    async def test_returns_none_if_thread_missing(self):
        svc, _, _ = _make_svc(thread=None)
        result = await svc.post_system_message("missing-t", "hello")
        assert result is None


class TestPostMessage:
    async def test_held_message_not_published(self):
        thread = _mock_thread()
        msg = _mock_message(is_held=True)
        svc, _, msg_repo = _make_svc(thread=thread, message=msg)

        # Simulate fraud detection holding the message
        with patch("main.app.domain.thread.service.di") as mock_di, \
             patch.object(svc, "_publish", AsyncMock()) as mock_pub, \
             patch.object(svc, "_emit_new_message_safe", AsyncMock()):
            fraud_svc = MagicMock()
            fraud_svc.scan = MagicMock(return_value=["phone"])
            fraud_svc.record_flag = AsyncMock()
            mock_di.__getitem__ = MagicMock(return_value=fraud_svc)

            from main.app.domain.thread.models import PostMessageDto
            dto = PostMessageDto(body="call me at +2348012345678")
            await svc.post_message("t-1", "u-1", SenderRole.CUSTOMER, dto)

        mock_pub.assert_not_called()

    async def test_thread_not_found_raises(self):
        svc, thread_repo, _ = _make_svc(thread=None)
        from main.app.domain.thread.models import PostMessageDto
        dto = PostMessageDto(body="hello")
        with pytest.raises(ResourceNotFoundException):
            await svc.post_message("missing-t", "u-1", SenderRole.CUSTOMER, dto)


class TestListMessages:
    async def test_returns_empty_list_for_empty_thread(self):
        svc, _, msg_repo = _make_svc()
        result = await svc.list_messages("t-1")
        assert result == []
        msg_repo.list_for_thread.assert_called_once_with("t-1", limit=50)
