"""process_retries — the sweep that re-dispatches RETRYING rows via MessageRouter.

Lifecycle under test (single Message entity, no DLQ):
  RETRYING + next_retry_at<=now → re-dispatch
    success                      → SENT
    transient failure            → retry_count+1, next interval from settings
    threshold exhausted          → FAILED permanent
    expires_at passed            → FAILED permanent, never dispatched
    next slot would be past TTL  → FAILED permanent
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.models import (
    EmailPayload,
    MessageChannel,
    MessageRecipient,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.service import MessagingService
from main.appodus_utils.integrations.messaging.services.rate_limiting import Throttler


def _retrying_row(row_id: str = "b" * 32, retry_count: int = 0,
                  expires_at=None) -> UpsertMessageDto:
    return UpsertMessageDto(
        id=row_id,
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient="user@example.com"),
        payload=EmailPayload(subject="Hello", html="<p>Hi</p>"),
        status=MessageStatus.RETRYING,
        retry_count=retry_count,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=expires_at,
        extras={},
    )


def _make_service(rows) -> MessagingService:
    svc = object.__new__(MessagingService)
    svc.router = AsyncMock()
    svc.message_service = AsyncMock()
    svc.message_service.get_retry_ready_messages = AsyncMock(
        return_value=SimpleNamespace(items=rows))
    svc.rate_limiter = AsyncMock()
    svc.throttler = Throttler(rps_limit=10_000)
    return svc


def _sent(message):
    message.status = MessageStatus.SENT
    message.provider = "SMTP"
    return message


class TestProcessRetries:
    async def test_successful_retry_marks_sent(self):
        row = _retrying_row()
        svc = _make_service([row])
        svc.router.send_message = AsyncMock(side_effect=_sent)

        stats = await svc.process_retries()

        assert stats["processed"] == 1
        assert svc.message_service.update_message_sent.call_args.args[0] == row.id
        svc.message_service.mark_message_failed.assert_not_called()

    async def test_transient_failure_schedules_next_interval(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [60, 300, 900])
        row = _retrying_row(retry_count=0)
        svc = _make_service([row])
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("still down"))

        before = datetime.now(timezone.utc)
        stats = await svc.process_retries()

        assert stats["retried"] == 1
        call = svc.message_service.schedule_message_retry.call_args
        assert call.kwargs["retry_count"] == 1
        delta = (call.kwargs["next_retry_at"] - before).total_seconds()
        assert 299 <= delta <= 310  # second rung of the ladder

    async def test_threshold_exhaustion_is_permanent(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [60, 300, 900])
        row = _retrying_row(retry_count=2)  # this is the 3rd and final retry
        svc = _make_service([row])
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("still down"))

        stats = await svc.process_retries()

        assert stats["permanent_failures"] == 1
        svc.message_service.schedule_message_retry.assert_not_called()
        svc.message_service.mark_message_failed.assert_called_once()

    async def test_expired_row_fails_without_dispatch(self):
        row = _retrying_row(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        svc = _make_service([row])

        stats = await svc.process_retries()

        assert stats["expired"] == 1
        svc.router.send_message.assert_not_called()
        svc.message_service.mark_message_failed.assert_called_once()
        assert "expire" in svc.message_service.mark_message_failed.call_args.args[1].lower()

    async def test_failure_with_next_slot_past_expiry_is_permanent(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [60, 300, 900])
        # Still valid now, but the next rung (300s) would land past the horizon.
        row = _retrying_row(
            retry_count=0,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=30))
        svc = _make_service([row])
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("still down"))

        stats = await svc.process_retries()

        assert stats["permanent_failures"] == 1
        svc.message_service.schedule_message_retry.assert_not_called()

    async def test_intervals_honoured_from_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "MESSAGING_RETRY_INTERVALS_SECONDS", [5, 7])
        row = _retrying_row(retry_count=0)
        svc = _make_service([row])
        svc.router.send_message = AsyncMock(side_effect=ConnectionError("down"))

        before = datetime.now(timezone.utc)
        await svc.process_retries()

        call = svc.message_service.schedule_message_retry.call_args
        delta = (call.kwargs["next_retry_at"] - before).total_seconds()
        assert 6 <= delta <= 12  # intervals[1] == 7

    async def test_one_bad_row_does_not_abort_the_sweep(self):
        good, bad = _retrying_row(row_id="c" * 32), _retrying_row(row_id="d" * 32)
        svc = _make_service([bad, good])

        async def _first_bad(message):
            if message.id == bad.id:
                raise ConnectionError("down")
            return _sent(message)

        svc.router.send_message = AsyncMock(side_effect=_first_bad)

        stats = await svc.process_retries()

        assert stats["processed"] == 1
        assert stats["retried"] == 1
