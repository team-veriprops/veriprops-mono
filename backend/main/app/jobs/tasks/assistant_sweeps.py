"""Pending assistant turn sweep (PRD §16.7, D93).

A web turn that needs the intent model is answered by the customer's second request. If that
request never comes — the tab closed in the milliseconds between the send and the turn call —
the turn stays pending until the page is next opened. This sweep answers it without waiting.
It is **not relied on** while every environment runs serverless, where the in-process
scheduler cannot be trusted; it becomes the dependable net on long-running hosts, with no
code change. Cadence is registered in ``app/jobs/scheduled.py``; disabled under test — tests
use ``POST /dev/assistant/sweep``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.jobs.exclusive import exclusive_job
from main.app.domain.communication.assistant.web import WebAssistantService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class AssistantSweepJobs:
    """Fresh-session wrapper around the pending-turn sweep."""

    def __init__(self, web_assistant_service: WebAssistantService):
        self._web_assistant_service = web_assistant_service

    @exclusive_job("assistant_pending_turns")
    async def run_pending_turn_sweep(self) -> Optional[dict]:
        return await self._web_assistant_service.sweep()


async def check_pending_assistant_turns() -> None:
    stats = await di[AssistantSweepJobs].run_pending_turn_sweep()
    if stats and any(stats.values()):
        logger.info("assistant pending-turn sweep: {}", stats)
