from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di

if TYPE_CHECKING:
    from loguru import Logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger: Logger = di['logger']
scheduler: AsyncIOScheduler = AsyncIOScheduler()


# TODO: dummy tasks, remove when real ones are implemented
def check_task_no_show_timeouts() -> None:
    pass
def check_task_pool_timeouts() -> None:
    pass

# Register task-monitor background jobs (pool timeout + no-show alerts)
scheduler.add_job(
    check_task_pool_timeouts,
    "interval",
    minutes=15,
    id="pool_timeout_check",
)

scheduler.add_job(
    check_task_no_show_timeouts,
    "interval",
    minutes=15,
    id="no_show_check",
)


def start_scheduler():
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
