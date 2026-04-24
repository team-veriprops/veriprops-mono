import asyncio
from dataclasses import dataclass
from typing import List, Callable, TypeVar, Awaitable

from main.appodus_utils.integrations.messaging.models import MessageRequest
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

T = TypeVar('T')


@dataclass
class BatchResult:
    successes: List[T]
    failures: List[T]
    processing_time: float


class BulkProcessor:
    def __init__(self, max_concurrency: int = 10, batch_size: int = 100):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_size = batch_size

    @resilience_manager.messaging_circuit_breaker()
    async def process_batch(
            self,
            messages: List[MessageRequest],
            process_fn: Callable[[MessageRequest], Awaitable[T]]
    ) -> BatchResult:
        """Process messages in parallel batches with backpressure"""
        start_time = asyncio.get_event_loop().time()
        results = []

        async def process_one(msg: MessageRequest):
            async with self.semaphore:
                try:
                    result = await process_fn(msg)
                    metrics_manager.track_message(
                        channel=msg.channel,
                        provider="bulk_processor",
                        status="success"
                    )
                    return True, result
                except Exception as e:
                    metrics_manager.track_message(
                        channel=msg.channel,
                        provider="bulk_processor",
                        status="failed"
                    )
                    return False, e

        # Process in batches
        for i in range(0, len(messages), self.batch_size):
            batch = messages[i:i + self.batch_size]
            tasks = [process_one(msg) for msg in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=False)
            results.extend(batch_results)

        # Categorize results
        successes = [r[1] for r in results if r[0]]
        failures = [r[1] for r in results if not r[0]]

        return BatchResult(
            successes=successes,
            failures=failures,
            processing_time=asyncio.get_event_loop().time() - start_time
        )

    async def process_with_retry(
            self,
            messages: List[MessageRequest],
            process_fn: Callable[[MessageRequest], Awaitable[T]],
            max_retries: int = 3
    ) -> BatchResult:
        """Process batch with automatic retries for failed items"""
        initial_result = await self.process_batch(messages, process_fn)

        if not initial_result.failures or max_retries <= 0:
            return initial_result

        # Exponential backoff for retries
        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            retry_result = await self.process_batch(
                initial_result.failures,
                process_fn
            )

            initial_result.successes.extend(retry_result.successes)
            initial_result.failures = retry_result.failures
            initial_result.processing_time += retry_result.processing_time

            if not initial_result.failures:
                break

        return initial_result
