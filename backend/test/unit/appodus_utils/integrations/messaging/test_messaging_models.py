"""Message DTO contracts the send/retry pipeline depends on.

Pydantic v2 treats ``Optional[X]`` without a default as REQUIRED — every partial
construction the services do (``_UpdateMessageDto(status=..., error=...)``,
``SearchMessageDto(page=..., status=...)``) must therefore keep explicit ``None``
defaults, or the whole bookkeeping layer raises ``ValidationError`` at runtime.
"""
from datetime import datetime, timedelta, timezone

from main.app.domain.message.models import (
    SearchMessageDto,
    UpsertMessageDto,
    _UpdateMessageDto,
)
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessagePriority,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)


def _email_request(**overrides) -> MessageRequest:
    kwargs = dict(
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
        payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>"),
        priority=MessagePriority.HIGH,
        extras={"user_id": "u-1", "trace_id": "t-1"},
    )
    kwargs.update(overrides)
    return MessageRequest(**kwargs)


class TestUpdateMessageDto:
    def test_partial_construction_status_and_error(self):
        dto = _UpdateMessageDto(status=MessageStatus.FAILED, error="boom")
        assert dto.status == MessageStatus.FAILED
        assert dto.error == "boom"

    def test_partial_construction_sent_fields(self):
        now = datetime.now(timezone.utc)
        dto = _UpdateMessageDto(status=MessageStatus.SENT, sent_at=now)
        assert dto.sent_at == now
        assert dto.retry_count is None

    def test_retry_schedule_shape(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=60)
        dto = _UpdateMessageDto(
            status=MessageStatus.RETRYING, retry_count=1, next_retry_at=when, error="x")
        assert dto.next_retry_at == when
        # retry_count=0 must survive an exclude_none dump (0 is not None)
        assert "retry_count" in _UpdateMessageDto(
            status=MessageStatus.RETRYING, retry_count=0, next_retry_at=when,
            error="x").model_dump(exclude_none=True)


class TestSearchMessageDto:
    def test_pending_sweep_shape(self):
        dto = SearchMessageDto(
            page=0, page_size=100,
            status=MessageStatus.PENDING,
            order_by="priority, date_created",
        )
        assert dto.status == MessageStatus.PENDING
        assert dto.channel is None

    def test_retry_ready_sweep_shape(self):
        dto = SearchMessageDto(
            page=0, page_size=100,
            status=MessageStatus.RETRYING,
            next_retry_at=datetime.now(timezone.utc),
            order_by="next_retry_at",
            where="next_retry_at <= ",
        )
        assert dto.status == MessageStatus.RETRYING
        assert dto.retry_count is None


class TestFromRequest:
    def test_maps_schedule_at_to_scheduled_at(self):
        when = datetime.now(timezone.utc) + timedelta(hours=2)
        message = UpsertMessageDto.from_request(_email_request(schedule_at=when))
        assert message.scheduled_at == when

    def test_carries_expires_at(self):
        horizon = datetime.now(timezone.utc) + timedelta(minutes=10)
        message = UpsertMessageDto.from_request(_email_request(expires_at=horizon))
        assert message.expires_at == horizon

    def test_preserves_channel_priority_extras(self):
        message = UpsertMessageDto.from_request(_email_request())
        assert message.channel == MessageChannel.EMAIL
        assert message.priority == MessagePriority.HIGH
        assert message.extras["trace_id"] == "t-1"
        assert message.status == MessageStatus.PENDING
        assert message.id is None          # id is assigned by the bookkeeping row
        assert message.expires_at is None  # no horizon unless the sender sets one
