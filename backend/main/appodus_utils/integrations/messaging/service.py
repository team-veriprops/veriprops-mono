import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.app.domain.message.service import MessageService
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationException,
    IntegrationValidationException,
    IntegrationRateLimitException,
)
from main.appodus_utils.integrations.messaging.models import (
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.router import MessageRouter
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter, Throttler

logger: logging.Logger = di['logger']

_EXPIRED_ERROR = "Expired before delivery (expires_at passed) — not re-dispatched"


@dataclass()
class BulkSendResult:
    total: int
    processing_time: float
    successes: List[UpsertMessageDto] = field(default_factory=list)
    failures: List[Exception] = field(default_factory=list)


@inject
class MessagingService:
    def __init__(
            self,
            router: MessageRouter,
            message_service: MessageService,
            rate_limiter: RateLimiter,
    ):
        self.router = router
        self.message_service = message_service
        self.rate_limiter = rate_limiter
        self.throttler = Throttler(rps_limit=settings.MESSAGING_RPS_LIMIT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(self, request: MessageRequest) -> UpsertMessageDto:
        """Process and send a message.

        Per-attempt retry, circuit breaking, and provider fallback are owned by
        MessageRouter. MessagingService owns conversion, rate limiting, metrics,
        and the bookkeeping lifecycle on the messages row: SENT on success,
        RETRYING (scheduled re-dispatch, capped by the interval ladder and the
        message's expires_at horizon) on transient failure, FAILED permanently
        on validation errors / exhausted horizon.
        """
        message = None
        start_time: Optional[datetime] = None

        try:
            message = UpsertMessageDto.from_request(request)
            await self._check_rate_limits(message)
            # Persist the bookkeeping row BEFORE dispatch and adopt its generated id:
            # update_message_sent (success) and the failure paths all update by id —
            # without it every delivered message was recorded as failed
            # ("Messages not found").
            await self._persist_message_row(message)

            async with self.throttler:
                start_time = datetime.now(timezone.utc)
                result = await self.router.send_message(message)

            self._track_success(message, result, start_time)
            if message.id:
                await self.message_service.update_message_sent(
                    message.id, datetime.now(timezone.utc), result
                )
            return result

        except IntegrationRateLimitException as e:
            # Rate limit violations are not transient for this attempt — the caller
            # (or a later business retry) re-enters the full pipeline.
            logger.warning("Rate limit hit: {}", e)
            raise

        except IntegrationValidationException as e:
            # Validation errors are permanent — retrying the same payload cannot succeed.
            logger.error("Validation error: {}", e)
            await self._record_failure(message, e, start_time, permanent=True)
            raise

        except Exception as e:
            logger.error("Failed to send message: {}", e, exc_info=True)
            await self._record_failure(message, e, start_time)
            raise IntegrationException(f"Failed to send message: {e}") from e

    async def send_bulk(self, requests: List[MessageRequest]) -> BulkSendResult:
        """Send multiple messages concurrently, capped at MESSAGING_BULK_CONCURRENCY parallel sends.

        Each message goes through the full send_message path — rate limiting,
        throttling, metrics, and retry scheduling all apply per message.
        Failures are isolated: one failed message does not abort the rest.
        """
        start = datetime.now(timezone.utc)
        sem = asyncio.Semaphore(settings.MESSAGING_BULK_CONCURRENCY)

        async def _process_one(req: MessageRequest):
            async with sem:
                return await self.send_message(req)

        outcomes = await asyncio.gather(
            *[_process_one(req) for req in requests],
            return_exceptions=True,
        )

        successes = [r for r in outcomes if isinstance(r, UpsertMessageDto)]
        failures = [r for r in outcomes if isinstance(r, Exception)]
        processing_time = (datetime.now(timezone.utc) - start).total_seconds()

        return BulkSendResult(
            total=len(requests),
            successes=successes,
            failures=failures,
            processing_time=processing_time
        )

    async def process_retries(self, max_batch_size: int = 100) -> Dict[str, Any]:
        """Re-dispatch RETRYING messages whose next_retry_at has passed.

        Runs from the scheduler sweep (and the admin sweeps endpoint). Each row is
        re-sent through MessageRouter — fresh provider selection, per-provider
        circuits. Outcomes: SENT on success; RETRYING with the next interval rung
        on transient failure; FAILED permanently once the interval ladder is
        exhausted or the message's expires_at horizon would be crossed. Rows whose
        expires_at already passed are failed without dispatching (a late OTP or
        reset link is useless — or worse, stale).
        """
        now = datetime.now(timezone.utc)
        ready = await self.message_service.get_retry_ready_messages(now, max_batch_size)
        stats = {"processed": 0, "retried": 0, "permanent_failures": 0, "expired": 0}

        for message in ready.items:
            if message.expires_at and message.expires_at <= datetime.now(timezone.utc):
                await self.message_service.mark_message_failed(message.id, _EXPIRED_ERROR)
                stats["expired"] += 1
                continue

            try:
                start_time = datetime.now(timezone.utc)
                result = await self.router.send_message(message)
                self._track_success(message, result, start_time)
                await self.message_service.update_message_sent(
                    message.id, datetime.now(timezone.utc), result
                )
                stats["processed"] += 1
            except Exception as e:
                logger.warning("Retry dispatch failed for message '{}': {}", message.id, e)
                error_msg = f"{e.__class__.__name__}: {str(e)}"[:500]
                retries_done = (message.retry_count or 0) + 1
                next_retry_at = self._next_retry_at(message, retries_done)
                if next_retry_at is None:
                    await self.message_service.mark_message_failed(message.id, error_msg)
                    stats["permanent_failures"] += 1
                else:
                    await self.message_service.schedule_message_retry(
                        message.id, retry_count=retries_done,
                        next_retry_at=next_retry_at, error=error_msg,
                    )
                    stats["retried"] += 1

        return stats

    async def get_message_status(self, message_id: str) -> UpsertMessageDto:
        """Get current message status, syncing from provider if pending."""
        message = await self.message_service.get_message_by_id(message_id)
        if not message:
            raise IntegrationValidationException("Message not found")

        if message.status == MessageStatus.PENDING and message.provider:
            provider_status = await self.router.get_message_status(
                message.provider,
                message.provider_id,
            )
            if provider_status is not None and provider_status != message.status:
                message.status = MessageStatus(provider_status)
                await self.message_service.update_message_status(
                    message_id, message.status
                )

        return message

    # ------------------------------------------------------------------
    # Supporting methods
    # ------------------------------------------------------------------

    async def _check_rate_limits(self, message: UpsertMessageDto) -> None:
        tenant = message.extras.get("tenant", "default")
        await self.rate_limiter.check_limit(
            f"{message.channel.value}:{tenant}"
        )

    @staticmethod
    def _track_success(
        message: UpsertMessageDto,
        result: UpsertMessageDto,
        start_time: datetime,
    ) -> None:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        metrics_manager.track_message(
            channel=message.channel.value,
            provider=result.provider or "unknown",
            status="success",
            duration=duration,
        )

    async def _persist_message_row(self, message: UpsertMessageDto) -> None:
        """Best-effort creation of the message bookkeeping row — bookkeeping must never
        block an actual delivery. On success the row's generated id is adopted onto the
        in-flight DTO so the post-dispatch status updates target the right row; on
        failure the id stays None and those updates are skipped."""
        try:
            created = await self.message_service.create_message(message)
            message.id = created.id
        except Exception as e:  # noqa: BLE001 — bookkeeping only
            logger.warning("Message bookkeeping row create failed: {}", e)

    @staticmethod
    def _next_retry_at(message: UpsertMessageDto, retries_done: int) -> Optional[datetime]:
        """Next re-dispatch time, or None when the message must fail permanently.

        None when the interval ladder (threshold = its length) is exhausted, or when
        the candidate slot would land on/after the message's expires_at horizon.
        """
        intervals = settings.MESSAGING_RETRY_INTERVALS_SECONDS
        if retries_done >= len(intervals):
            return None
        candidate = datetime.now(timezone.utc) + timedelta(seconds=intervals[retries_done])
        if message.expires_at and candidate >= message.expires_at:
            return None
        return candidate

    async def _record_failure(
        self,
        message: Optional[UpsertMessageDto],
        error: Exception,
        start_time: Optional[datetime] = None,
        *,
        permanent: bool = False,
    ) -> None:
        """Record a dispatch failure on the bookkeeping row.

        Transient failures are scheduled for the retry sweep (first ladder rung,
        expiry-aware); permanent ones (validation, exhausted horizon) are marked
        FAILED outright. Gracefully exits when message is None (conversion failed
        before a DTO existed) or the bookkeeping row was never created (id None).
        """
        if message is None:
            return

        error_msg = f"{error.__class__.__name__}: {str(error)}"[:500]

        duration = (
            (datetime.now(timezone.utc) - start_time).total_seconds()
            if start_time else 0
        )
        metrics_manager.track_message(
            channel=message.channel.value,
            provider=message.provider or "unknown",
            status="failed",
            duration=duration,
        )

        if not message.id:
            return

        try:
            next_retry_at = None if permanent else self._next_retry_at(message, retries_done=0)
            if next_retry_at is None:
                await self.message_service.mark_message_failed(message.id, error_msg)
            else:
                await self.message_service.schedule_message_retry(
                    message.id, retry_count=0, next_retry_at=next_retry_at, error=error_msg,
                )
        except Exception as bookkeeping_error:
            logger.error(
                "Failed to record message failure {}: {}",
                message.id, bookkeeping_error,
                exc_info=True,
            )
