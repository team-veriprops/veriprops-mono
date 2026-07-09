import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kink import inject, di
from pydantic import Field

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.app.domain.message.service import MessageService
from main.appodus_utils.db.models import Object
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
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.dlq import DeadLetterQueue
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter, Throttler

logger: logging.Logger = di['logger']


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
            dlq: DeadLetterQueue,
            rate_limiter: RateLimiter,
    ):
        self.router = router
        self.message_service = message_service
        self.dlq = dlq
        self.rate_limiter = rate_limiter
        self.throttler = Throttler(rps_limit=settings.MESSAGING_RPS_LIMIT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(self, request: MessageRequest) -> UpsertMessageDto:
        """Process and send a message.

        Retry, circuit breaking, and provider fallback are entirely owned by
        MessageRouter. MessagingService owns conversion, rate limiting, metrics,
        and DLQ registration.
        """
        message = None
        start_time: datetime

        try:
            message = UpsertMessageDto.from_request(request)
            await self._check_rate_limits(message)

            async with self.throttler:
                start_time = datetime.now(timezone.utc)
                result = await self.router.send_message(message)

            self._track_success(message, result, start_time)
            await self.message_service.update_message_sent(
                message.id, datetime.now(timezone.utc), result
            )
            return result

        except IntegrationRateLimitException as e:
            # Rate limit violations are not transient — do not DLQ.
            logger.warning("Rate limit hit: {}", e)
            raise

        except IntegrationValidationException as e:
            # Validation errors are not transient — do not DLQ.
            logger.error("Validation error: {}", e)
            raise

        except Exception as e:
            logger.error("Failed to send message: {}", e, exc_info=True)
            await self._handle_failure(message, e, start_time)
            raise IntegrationException(f"Failed to send message: {e}") from e

    async def send_bulk(self, requests: List[MessageRequest]) -> BulkSendResult:
        """Send multiple messages concurrently, capped at MESSAGING_BULK_CONCURRENCY parallel sends.

        Each message goes through the full send_message path — rate limiting,
        throttling, metrics, and DLQ registration all apply per message.
        Failures are isolated: one failed message does not abort the rest.
        """
        start = datetime.now(timezone.utc)
        sem = asyncio.Semaphore(settings.MESSAGING_BULK_CONCURRENCY)

        async def _process_one(req: MessageRequest):
            async with sem:
                return await self.send_message(req)
            return None

        outcomes = await asyncio.gather(
            *[_process_one(req) for req in requests],
            return_exceptions=True,
        )

        successes = [r for r in outcomes if not isinstance(r, UpsertMessageDto)]
        failures = [r for r in outcomes if isinstance(r, Exception)]
        processing_time = (datetime.now(timezone.utc) - start).total_seconds()

        return BulkSendResult(
            total=len(requests),
            successes=successes,
            failures=failures,
            processing_time=processing_time
        )

    async def process_dlq_retries(self, max_batch_size: int = 100) -> Dict[str, Any]:
        """Process messages in the DLQ that are ready for retry."""
        return await self.dlq.process_retries(max_batch_size)

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

    async def _handle_failure(
        self,
        message: Optional[UpsertMessageDto],
        error: Exception,
        start_time: Optional[datetime] = None,
    ) -> None:
        """Record failure status and enqueue in DLQ.

        Gracefully exits when message is None — this occurs when conversion
        itself fails before a UpsertMessageDto is ever produced.
        """
        if message is None:
            return

        error_msg = f"{error.__class__.__name__}: {str(error)}"
        message.status = MessageStatus.FAILED
        message.error = error_msg[:500]

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

        try:
            await self.message_service.update_message_status(
                message.id, message.status, message.error
            )
            await self.dlq.add_to_dlq(
                message,
                error_msg,
                extras={"trace_id": message.extras.get("trace_id")},
            )
            logger.info("Message '{}' added to DLQ", message.id)
        except Exception as dlq_error:
            logger.error(
                "Failed to handle message failure {}: {}",
                message.id, dlq_error,
                exc_info=True,
            )
