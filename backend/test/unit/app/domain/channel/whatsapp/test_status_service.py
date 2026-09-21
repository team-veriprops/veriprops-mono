"""WhatsAppStatusService — Meta's delivery and read receipts (§26.3.3, D92).

A receipt moves the message's delivery state forward for the console's ticks, and a read
receipt counts as the customer reading the thread, so it clears their portal unread badge.
Receipts arrive late, out of order and more than once, so every effect is forward-only.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.domain.channel.whatsapp.status.service import WhatsAppStatusService
from main.app.domain.communication.chat_message.models import ChannelDeliveryStatus
from main.app.domain.communication.conversation.models import ConversationChannel
from main.app.domain.communication.conversation_participant.models import ConversationParticipant
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundWhatsAppStatus,
    WhatsAppDeliveryStatus,
)

OWNER = "3f2c0d4e-0000-4000-8000-000000000001"
SENT_AT = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
RECEIPT_AT = datetime(2026, 9, 17, 9, 5, tzinfo=timezone.utc)


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


@pytest.fixture
def published(monkeypatch):
    events = []
    monkeypatch.setattr(
        "main.app.domain.channel.whatsapp.status.service.publish_domain_event",
        AsyncMock(side_effect=events.append),
    )
    return events


def _message(channel_status=ChannelDeliveryStatus.SENT.value):
    return SimpleNamespace(
        id="msg-1", conversation_id="conv-1", channel_status=channel_status,
        channel_status_at=SENT_AT, delivered_at=SENT_AT, date_created=SENT_AT,
    )


def _service(message, *, owner=OWNER, participants=()):
    svc = object.__new__(WhatsAppStatusService)
    svc._chat_message_repo = MagicMock(
        get_outbound_by_external_id=AsyncMock(return_value=message), _session=MagicMock()
    )
    svc._conversation_repo = MagicMock(get_model=AsyncMock(return_value=SimpleNamespace(
        id="conv-1", channel=ConversationChannel.WHATSAPP.value, created_by=owner,
    )))
    svc._participants = MagicMock(advance_read=AsyncMock(return_value=True))
    svc._participants._participant_repo = MagicMock(
        list_for_conversation=AsyncMock(return_value=list(participants))
    )
    svc._message_service = MagicMock(
        mark_delivered_by_provider_id=AsyncMock(), mark_failed_by_provider_id=AsyncMock()
    )
    return svc


def _receipt(status, **overrides):
    values = dict(wamid="wamid.OUT1", status=status, timestamp=RECEIPT_AT)
    values.update(overrides)
    return InboundWhatsAppStatus(**values)


class TestTicks:
    async def test_a_receipt_moves_the_message_forward(self, published):
        message = _message()
        svc = _service(message)

        assert await svc.apply(_receipt(WhatsAppDeliveryStatus.DELIVERED)) is True

        assert message.channel_status == ChannelDeliveryStatus.DELIVERED.value
        assert message.channel_status_at == RECEIPT_AT
        svc._message_service.mark_delivered_by_provider_id.assert_awaited_once_with("wamid.OUT1", RECEIPT_AT)

    async def test_a_late_receipt_never_moves_it_back(self, published):
        message = _message(channel_status=ChannelDeliveryStatus.READ.value)
        svc = _service(message)

        assert await svc.apply(_receipt(WhatsAppDeliveryStatus.DELIVERED)) is False

        assert message.channel_status == ChannelDeliveryStatus.READ.value
        assert published == []

    async def test_an_unknown_wamid_is_a_no_op(self, published):
        # Sent before receipts were tracked, or a template with no console copy.
        svc = _service(None)

        assert await svc.apply(_receipt(WhatsAppDeliveryStatus.READ)) is False

        svc._participants.advance_read.assert_not_awaited()

    async def test_a_failure_is_recorded_with_metas_codes(self, published):
        message = _message()
        svc = _service(message)

        await svc.apply(_receipt(WhatsAppDeliveryStatus.FAILED, error_codes=[131047]))

        assert message.channel_status == ChannelDeliveryStatus.FAILED.value
        svc._message_service.mark_failed_by_provider_id.assert_awaited_once()
        assert "131047" in svc._message_service.mark_failed_by_provider_id.await_args.args[1]

    async def test_the_threads_members_are_nudged_to_refresh(self, published):
        members = [
            ConversationParticipant(user_id=OWNER),
            ConversationParticipant(user_id="admin-1"),
            ConversationParticipant(user_id="former", visible_until=SENT_AT),
        ]
        svc = _service(_message(), participants=members)

        await svc.apply(_receipt(WhatsAppDeliveryStatus.DELIVERED))

        [event] = published
        assert event.type == EventType.MESSAGE_STATUS_CHANGED
        assert set(event.recipient_user_ids) == {OWNER, "admin-1"}


class TestReadReceiptsClearThePortalBadge:
    async def test_reading_on_whatsapp_reads_the_thread_up_to_that_message(self, published):
        svc = _service(_message())

        await svc.apply(_receipt(WhatsAppDeliveryStatus.READ))

        # Up to when the message reached the thread, not when the receipt came in: later
        # portal-only messages have not been seen.
        svc._participants.advance_read.assert_awaited_once_with("conv-1", OWNER, SENT_AT)

    async def test_a_delivered_receipt_is_not_a_read(self, published):
        svc = _service(_message())

        await svc.apply(_receipt(WhatsAppDeliveryStatus.DELIVERED))

        svc._participants.advance_read.assert_not_awaited()

    async def test_an_unlinked_numbers_thread_has_no_one_to_mark(self, published):
        svc = _service(_message(), owner=None)

        await svc.apply(_receipt(WhatsAppDeliveryStatus.READ))

        svc._participants.advance_read.assert_not_awaited()
