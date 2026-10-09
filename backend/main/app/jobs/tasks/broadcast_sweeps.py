"""Admin broadcast jobs (PRD §18.1, decision-log S22): start scheduled sends, then fan out.

Two jobs over ``BroadcastService``, each in an ``ALWAYS_NEW`` transaction under its own job lock:

* ``check_scheduled_broadcasts`` claims SCHEDULED broadcasts whose time has passed (→ SENDING).
* ``check_broadcast_fanout`` sends SENDING broadcasts page by page. **Each page is its own
  transaction**, so a run that dies part-way keeps every page it finished and the next run
  resumes from the cursor; a run takes pages while they make progress, up to
  ``BROADCAST_FANOUT_MAX_PAGES_PER_RUN``, so one large audience cannot hold the tick.

Cadence is registered in ``app/jobs/registry.py``; nothing runs them under test — tests call the
service, or the admin ``POST /admin/broadcasts/sweeps/scheduled`` endpoint.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.jobs.exclusive import exclusive_job
from main.app.domain.broadcast.service import BroadcastService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class BroadcastSweepJobs:
    """Fresh-session wrappers around the scheduled-broadcast start and the fan-out (§18.1)."""

    def __init__(self, broadcast_service: BroadcastService):
        self._broadcast = broadcast_service

    @exclusive_job("scheduled_broadcasts")
    async def run_scheduled_broadcast_sweep(self) -> Optional[int]:
        return await self._broadcast.sweep_scheduled_broadcasts()

    @exclusive_job("broadcast_fanout")
    async def run_fanout_page(self) -> Optional[bool]:
        return await self._broadcast.fanout_next_page()


async def check_scheduled_broadcasts() -> None:
    started = await di[BroadcastSweepJobs].run_scheduled_broadcast_sweep()
    if started:
        logger.info("broadcast sweep started {} scheduled broadcast(s)", started)


async def check_broadcast_fanout() -> None:
    pages = 0
    while pages < settings.BROADCAST_FANOUT_MAX_PAGES_PER_RUN:
        # None: another worker holds the job; False: nothing left to send this run.
        if not await di[BroadcastSweepJobs].run_fanout_page():
            break
        pages += 1
    if pages:
        logger.info("broadcast fan-out sent {} page(s)", pages)
