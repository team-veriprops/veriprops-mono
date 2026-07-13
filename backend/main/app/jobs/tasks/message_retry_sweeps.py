"""Outbound-message retry sweep (messaging delivery pipeline).

Re-dispatches ``RETRYING`` messages whose ``next_retry_at`` has passed; the
backoff ladder (``MESSAGING_RETRY_INTERVALS_SECONDS``) and the ``expires_at``
horizon for time-bound content (OTPs, reset links) live in ``MessagingService``.
This module wraps ``process_retries`` in an ``ALWAYS_NEW`` transactional job
(fresh session per sweep). Cadence is registered in ``app/jobs/scheduled.py``
(every minute — the first ladder rung defaults to 60s); disabled under test —
tests use the admin ``POST /messages/sweeps/retries`` endpoint or call
``process_retries`` directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.appodus_utils.integrations.messaging.service import MessagingService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class MessageRetrySweepJobs:
    """Fresh-session wrapper around the outbound-message retry sweep: re-dispatches
    RETRYING messages whose next_retry_at has passed (backoff ladder + expires_at
    horizon live in MessagingService)."""

    def __init__(self, messaging_service: MessagingService):
        self._messaging_service = messaging_service

    async def run_message_retry_sweep(self) -> dict:
        return await self._messaging_service.process_retries()


async def check_message_retries() -> None:
    stats = await di[MessageRetrySweepJobs].run_message_retry_sweep()
    if any(stats.values()):
        logger.info("message-retry sweep: {}", stats)
