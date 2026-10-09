"""The in-process sweep runner, for local and long-running hosts.

What runs, and when, is declared in ``app/jobs/registry.py``; this module only supplies a
clock. It holds a single APScheduler job that calls the sweep tick (``app/jobs/tick.py``) every
minute — the same tick the Cloudflare Cron Worker calls on the deployed serverless
environments, where an in-process scheduler cannot be trusted to fire. Because both runners
claim each due job on ``scheduled_job_runs`` before running it, any number of them (the Worker,
one scheduler per worker process) run each fire once.

The scheduler is skipped under the test environment; tests invoke the sweep methods (or the
admin dev sweep endpoints) directly for determinism (decision-log D12: sweeps are claim-based
and idempotent, safe alongside request traffic).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di

from main.app.config.settings import settings
from main.app.domain.scheduled_job.models import SweepJobOutcome
from main.appodus_utils.config.settings import Environment
from main.app.jobs.tick import run_sweep_tick

if TYPE_CHECKING:
    from loguru import Logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger: Logger = di['logger']
scheduler: AsyncIOScheduler = AsyncIOScheduler()

TICK_JOB_ID = "sweep_tick"


async def _scheduled_tick() -> None:
    result = await run_sweep_tick()
    acted = [job for job in result.jobs if job.outcome in (SweepJobOutcome.RAN, SweepJobOutcome.FAILED)]
    if acted:
        logger.info("sweep tick: {}", ", ".join(f"{job.name}={job.outcome.value}" for job in acted))


# One minute is the finest cadence in the registry; APScheduler's default max_instances=1 skips
# a minute rather than overlap a tick still running.
scheduler.add_job(_scheduled_tick, "interval", minutes=1, id=TICK_JOB_ID)


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
