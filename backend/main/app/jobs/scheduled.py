"""Background scheduler (PRD §7.2 timeout sweeps, §6.4 SLA shedding).

The time-driven task automation — no-show reclaim and broadcast-pool starvation
escalation — lives as pure, tested methods on ``VerificationTaskService``. Here we
wrap each in an ``ALWAYS_NEW`` transactional job (a fresh session per sweep, mirroring
``DataSeeder``) and register it on APScheduler. Sweeps are claim-based and idempotent,
so they are safe to run concurrently with request traffic (decision-log D12).

The scheduler is skipped under the test environment; tests invoke the sweep methods
(or the admin dev sweep endpoint) directly for determinism.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.config.settings import Environment
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger: Logger = di['logger']
scheduler: AsyncIOScheduler = AsyncIOScheduler()


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class TaskSweepJobs:
    """Fresh-session wrappers around the task timeout sweeps so the scheduler can
    run them outside a request lifecycle."""

    def __init__(self, task_service: VerificationTaskService):
        self._task_service = task_service

    async def run_no_show_sweep(self) -> int:
        return await self._task_service.sweep_no_show()

    async def run_pool_starvation_sweep(self) -> int:
        return await self._task_service.sweep_pool_starvation()


async def check_task_no_show_timeouts() -> None:
    reclaimed = await di[TaskSweepJobs].run_no_show_sweep()
    if reclaimed:
        logger.info("no-show sweep reclaimed {} task(s)", reclaimed)


async def check_task_pool_timeouts() -> None:
    escalated = await di[TaskSweepJobs].run_pool_starvation_sweep()
    if escalated:
        logger.info("pool-starvation sweep escalated {} task(s)", escalated)


# Register task-monitor background jobs (pool timeout + no-show reclaim).
scheduler.add_job(check_task_pool_timeouts, "interval", minutes=15, id="pool_timeout_check")
scheduler.add_job(check_task_no_show_timeouts, "interval", minutes=15, id="no_show_check")


def start_scheduler():
    # Determinism: no wall-clock automation under test; sweeps run directly there.
    if settings.ENVIRONMENT == Environment.TEST:
        logger.info("Scheduler disabled under test environment")
        return
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    try:
        scheduler.start()
        logger.info("APScheduler started successfully")

        for job in scheduler.get_jobs():
            logger.info(
                "Registered job: id={} next_run={} trigger={}",
                job.id,
                job.next_run_time,
                job.trigger,
            )

    except Exception:
        logger.exception("Failed to start APScheduler")
        raise


def stop_scheduler():
    if not scheduler.running:
        logger.warning("Scheduler is not running")
        return

    try:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shutdown successfully")

    except Exception:
        logger.exception("Failed to shutdown APScheduler")
        raise
