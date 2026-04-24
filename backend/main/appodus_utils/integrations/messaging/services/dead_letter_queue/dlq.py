import logging
from datetime import datetime, timedelta
from typing import Optional

from kink import inject, di

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.models import CreateDLQDto, QueryDLQDto, DLQStatus
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.service import DLQService
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils import Utils

logger: logging.Logger = di['logger']


@inject
class DeadLetterQueue:
    def __init__(self, dlq_service: DLQService):
        self._dlq_service = dlq_service
        self.retry_intervals = [60, 300, 900]  # 1m, 5m, 15m in seconds

    async def add_to_dlq(
            self,
            message: UpsertMessageDto,
            error: str,
            extras: Optional[dict] = None
    ) -> QueryDLQDto:
        """Add failed message to DLQ with initial retry policy"""
        entry = CreateDLQDto(
            original_message=message,
            error=str(error),
            attempts=0,
            next_retry_at=Utils.datetime_now() + timedelta(seconds=self.retry_intervals[0]),
            status=DLQStatus.PENDING,
            extras=extras or {}
        )

        created = await self._dlq_service.create(entry)
        metrics_manager.dlq_operations.labels(
            operation="add",
            channel=message.channel,
            provider=message.provider
        ).inc()

        return created

    async def process_retries(self, max_batch_size: int = 100) -> dict:
        """Process messages ready for retry and return stats"""
        now = Utils.datetime_now()
        ready_messages = await self._dlq_service.get_ready_for_retry(now, max_batch_size)
        stats = {
            "processed": 0,
            "permanent_failures": 0,
            "retried": 0
        }

        for msg in ready_messages.items:
            if msg.attempts >= len(self.retry_intervals):
                await self._mark_as_failed(msg)
                stats["permanent_failures"] += 1
                continue

            try:
                # Get original processing function from extras
                process_fn = msg.extras.get("process_fn")
                if not process_fn:
                    logger.error(f"No process_fn in extras for DLQ entry {msg.id}")
                    await self._mark_as_failed(msg)
                    continue

                # Retry the message
                await self._dlq_service.update_status(msg.id, DLQStatus.RETRYING)
                result = await process_fn(msg.original_message)

                if result.status == "sent":
                    await self._dlq_service.mark_as_processed(msg.id)
                    stats["processed"] += 1
                else:
                    await self._schedule_next_retry(msg)
                    stats["retried"] += 1

            except Exception as e:
                logger.error(f"Retry failed for DLQ entry {msg.id}: {str(e)}")
                await self._schedule_next_retry(msg)
                stats["retried"] += 1

        return stats

    async def _schedule_next_retry(self, entry: QueryDLQDto):
        next_attempt = entry.attempts + 1
        if next_attempt >= len(self.retry_intervals):
            await self._mark_as_failed(entry)
        else:
            next_interval = self.retry_intervals[next_attempt]
            await self._dlq_service.schedule_retry(
                entry.id,
                next_attempt,
                Utils.datetime_now() + timedelta(seconds=next_interval)
            )

    async def _mark_as_failed(self, entry: QueryDLQDto):
        await self._dlq_service.mark_as_failed(entry.id)
        metrics_manager.dlq_operations.labels(
            operation="permanent_failure",
            channel=entry.original_message.channel,
            provider=entry.original_message.provider
        ).inc()
