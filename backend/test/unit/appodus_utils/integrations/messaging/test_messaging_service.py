"""MessagingService send-path bookkeeping — router/message-service mocked.

Covers the contract the drive-through exposed as broken: the bookkeeping row is
created BEFORE dispatch and its generated id is adopted onto the in-flight DTO,
success updates that same id to SENT, transient failure schedules a retry with
the first configured interval, non-transient failures fail permanently, and
send_bulk buckets successes/failures correctly.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationException,
    IntegrationValidationException,
)
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.service import MessagingService
from main.appodus_utils.integrations.messaging.services.rate_limiting import Throttler

ROW_ID = "a" * 32


def _email_request(**overrides) -> MessageRequest:
    kwargs = dict(
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
        payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>"),
        extras={"user_id": "u-1"},
    )
    kwargs.update(overrides)
    return MessageRequest(**kwargs)


def _sent_result(message: UpsertMessageDto) -> UpsertMessageDto:
    message.status = MessageStatus.SENT
    message.provider = "SMTP"
    return message


def _make_service() -> MessagingService:
    svc = object.__new__(MessagingService)
    svc.router = AsyncMock()
    svc.message_service = AsyncMock()
    svc.message_service.create_message = AsyncMock(
        side_effect=lambda dto: SimpleNamespace(id=ROW_ID))
    svc.rate_limiter = AsyncMock()
    svc.throttler = Throttler(rps_limit=10_000)
    return svc


class TestSendMessage:
    async def test_success_adopts_row_id_and_marks_sent(self):
        svc = _make_service()
        svc.router.send_message = AsyncMock(side_effect=_sent_result)

        result = await svc.send_message(_email_request())

        assert result.status == MessageStatus.SENT
        (message,) = svc.message_service.create_message.call_args.args
        assert message.id == ROW_ID  # generated id adopted before dispatch
        sent_call = svc.message_service.update_message_sent.call_args
        assert sent_call.args[0] == ROW_ID
        svc.message_service.schedule_message_retry.assert_not_called()
        svc.message_service.mark_message_failed.assert_not_called()

    async def test_transient_failure_schedules_first_retry(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [60, 300, 900])
        svc = _make_service()
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("smtp down"))

        before = datetime.now(timezone.utc)
        with pytest.raises(IntegrationException):
            await svc.send_message(_email_request())

        call = svc.message_service.schedule_message_retry.call_args
        assert call.kwargs["retry_count"] == 0
        assert "smtp down" in call.kwargs["error"]
        delta = (call.kwargs["next_retry_at"] - before).total_seconds()
        assert 59 <= delta <= 70  # first interval of the ladder
        assert call.args[0] == ROW_ID or call.kwargs.get("message_id") == ROW_ID
        svc.message_service.update_message_sent.assert_not_called()

    async def test_expired_message_fails_permanently_on_first_failure(self, monkeypatch):
        """A retry that would land past expires_at must not be scheduled."""
        monkeypatch.setattr(
            settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [60, 300, 900])
        svc = _make_service()
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("smtp down"))
        horizon = datetime.now(timezone.utc) + timedelta(seconds=5)  # < first interval

        with pytest.raises(IntegrationException):
            await svc.send_message(_email_request(expires_at=horizon))

        svc.message_service.schedule_message_retry.assert_not_called()
        svc.message_service.mark_message_failed.assert_called_once()

    async def test_validation_failure_is_permanent(self):
        svc = _make_service()
        svc.router.send_message = AsyncMock(
            side_effect=IntegrationValidationException("bad payload"))

        with pytest.raises(IntegrationValidationException):
            await svc.send_message(_email_request())

        svc.message_service.schedule_message_retry.assert_not_called()
        svc.message_service.mark_message_failed.assert_called_once()

    async def test_bookkeeping_create_failure_does_not_block_delivery(self):
        """Bookkeeping is best-effort — a failed row insert must not stop the send."""
        svc = _make_service()
        svc.message_service.create_message = AsyncMock(side_effect=RuntimeError("db down"))
        svc.router.send_message = AsyncMock(side_effect=_sent_result)

        result = await svc.send_message(_email_request())

        assert result.status == MessageStatus.SENT
        svc.message_service.update_message_sent.assert_not_called()  # no row id to update


class TestSendBulk:
    async def test_buckets_successes_and_failures(self):
        svc = _make_service()

        calls = {"n": 0}

        async def _alternate(message):
            calls["n"] += 1
            if calls["n"] % 2 == 0:
                raise ConnectionError("flaky")
            return _sent_result(message)

        svc.router.send_message = AsyncMock(side_effect=_alternate)

        result = await svc.send_bulk([_email_request(), _email_request(),
                                      _email_request(), _email_request()])

        assert result.total == 4
        assert len(result.successes) == 2
        assert len(result.failures) == 2
        assert all(isinstance(m, UpsertMessageDto) for m in result.successes)
        assert all(isinstance(e, Exception) for e in result.failures)
