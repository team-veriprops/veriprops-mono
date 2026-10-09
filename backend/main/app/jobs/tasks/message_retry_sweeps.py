"""Outbound-message drain (messaging delivery pipeline).

Sends every message whose ``next_retry_at`` has passed: queued deliveries (PENDING, a
broadcast's emails) and due retries (RETRYING). The backoff ladder
(``MESSAGING_RETRY_INTERVALS_SECONDS``) and the ``expires_at`` horizon for time-bound
content (OTPs, reset links) live in ``MessagingService``. This module wraps
``drain_due_messages`` in an ``ALWAYS_NEW`` transactional job (fresh session per run).
Cadence is registered in ``app/jobs/registry.py`` (every minute — the first ladder rung
defaults to 60s); nothing runs it under test — tests use the admin
``POST /messages/sweeps/retries`` endpoint or call ``drain_due_messages`` directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.jobs.exclusive import exclusive_job
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
    """Fresh-session wrapper around the outbound-message drain: sends queued deliveries and
    due retries (backoff ladder + expires_at horizon live in MessagingService)."""

    def __init__(self, messaging_service: MessagingService):
        self._messaging_service = messaging_service

    @exclusive_job("message_retries")
    async def run_message_retry_sweep(self) -> Optional[dict]:
        return await self._messaging_service.drain_due_messages()


async def check_message_retries() -> None:
    stats = await di[MessageRetrySweepJobs].run_message_retry_sweep()
    if stats and any(stats.values()):
        logger.info("message drain: {}", stats)
