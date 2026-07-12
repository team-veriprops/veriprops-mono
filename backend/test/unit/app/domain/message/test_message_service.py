"""MessageService bookkeeping — repo mocked, session stubbed.

The regression that mattered live: ``create_message`` must return a DTO whose id
is the row's generated UUID in hex string form (``BaseEntity.id`` is a
``uuid.UUID``; the CamelModel UUID→hex coercion only runs on dict input, so
validating the ORM row with ``from_attributes=True`` blew up and left every
message row orphaned in PENDING).
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.message.models import Message, UpsertMessageDto
from main.app.domain.message.service import MessageService
from main.appodus_utils import Utils
from main.appodus_utils.decorators import transactional as transactional_module
from main.appodus_utils.integrations.messaging.models import (
    EmailPayload,
    MessageChannel,
    MessagePriority,
    MessageRecipient,
    MessageStatus,
)


@pytest.fixture(autouse=True)
def mock_db_session(monkeypatch):
    """MessageService methods are ALWAYS_NEW-transactional — stub the session
    factory the decorator opens instead of the ambient context session."""
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    @asynccontextmanager
    async def _new_session():
        yield session

    monkeypatch.setattr(transactional_module, "create_new_db_session", _new_session)
    yield session


def _make_service() -> MessageService:
    svc = object.__new__(MessageService)
    svc._message_repo = AsyncMock()
    svc._message_validator = AsyncMock()
    return svc


def _upsert_dto() -> UpsertMessageDto:
    return UpsertMessageDto(
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient="user@example.com"),
        payload=EmailPayload(subject="Hi", html="<p>Hi</p>"),
        extras={},
    )


def _orm_row(row_id: uuid.UUID) -> Message:
    now = datetime.now(timezone.utc)
    return Message(
        id=row_id,
        channel=MessageChannel.EMAIL.value,
        to={"recipient": "user@example.com"},
        payload={"subject": "Hi", "html": "<p>Hi</p>"},
        status=MessageStatus.PENDING.value,
        retry_count=0,
        priority=MessagePriority.NORMAL.value,
        extras={},
        date_created=now,
        date_updated=now,
        version=1,
        deleted=False,
    )


class TestCreateMessage:
    async def test_returns_dto_with_hex_id(self):
        svc = _make_service()
        row_id = Utils.generate_uuid() if hasattr(Utils, "generate_uuid") else uuid.uuid4()
        svc._message_repo.create_from_upsert = AsyncMock(return_value=_orm_row(row_id))

        created = await svc.create_message(_upsert_dto())

        assert created.id == row_id.hex  # UUID coerced to the 32-char wire form
        assert created.status == MessageStatus.PENDING


class TestRetryBookkeeping:
    async def test_schedule_message_retry_writes_retrying_state(self):
        svc = _make_service()
        when = datetime.now(timezone.utc) + timedelta(seconds=60)

        await svc.schedule_message_retry("a" * 32, retry_count=1,
                                         next_retry_at=when, error="smtp down")

        update = svc._message_repo.update.call_args.args[1]
        assert update["status"] == MessageStatus.RETRYING
        assert update["retry_count"] == 1
        assert update["next_retry_at"] == when

    async def test_mark_message_failed_is_permanent_failed_status(self):
        svc = _make_service()

        await svc.mark_message_failed("a" * 32, "threshold exhausted")

        update = svc._message_repo.update.call_args.args[1]
        assert update["status"] == MessageStatus.FAILED
        assert update["error"] == "threshold exhausted"

    async def test_update_message_delivered_uses_delivered_status(self):
        svc = _make_service()
        when = datetime.now(timezone.utc)

        await svc.update_message_delivered("a" * 32, when)

        update = svc._message_repo.update.call_args.args[1]
        assert update["status"] == MessageStatus.DELIVERED
