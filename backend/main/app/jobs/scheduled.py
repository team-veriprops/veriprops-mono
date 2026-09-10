"""Background scheduler wiring (PRD §11.4 timeout sweeps, §6.4 SLA shedding).

The individual sweep tasks — job wrappers plus their ``check_*`` entrypoints —
live one-file-per-concern under ``app/jobs/tasks/``. This module owns the
APScheduler instance, registers every entrypoint with its cadence (kept together
here so all cadences are visible in one place), and exposes start/stop for the
app lifespan.

The scheduler is skipped under the test environment; tests invoke the sweep
methods (or the admin dev sweep endpoint) directly for determinism (decision-log
D12: sweeps are claim-based and idempotent, safe alongside request traffic).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di

from main.app.config.settings import settings
from main.appodus_utils.config.settings import Environment
from main.app.jobs.tasks import (
    check_abandoned_drafts,
    check_commission_clearance,
    check_message_retries,
    check_referral_credits,
    check_scheduled_broadcasts,
    check_sla_breaches,
    check_task_no_show_timeouts,
    check_task_pool_timeouts,
)

if TYPE_CHECKING:
    from loguru import Logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger: Logger = di['logger']
scheduler: AsyncIOScheduler = AsyncIOScheduler()


# Register task-monitor background jobs (pool timeout + no-show reclaim) + SLA-breach sweep.
scheduler.add_job(check_task_pool_timeouts, "interval", minutes=15, id="pool_timeout_check")
scheduler.add_job(check_task_no_show_timeouts, "interval", minutes=15, id="no_show_check")
scheduler.add_job(check_sla_breaches, "interval", minutes=30, id="sla_breach_check")
scheduler.add_job(check_commission_clearance, "interval", minutes=60, id="commission_clearance_check")
# Growth sweeps (§17.1): abandonment recovery (hourly) + referral-credit clearance (daily-ish).
scheduler.add_job(check_abandoned_drafts, "interval", minutes=60, id="abandonment_recovery_check")
scheduler.add_job(check_referral_credits, "interval", minutes=180, id="referral_credit_check")
# Scheduled admin broadcasts (§18.1): send those whose time has passed.
scheduler.add_job(check_scheduled_broadcasts, "interval", minutes=5, id="scheduled_broadcast_check")
# Outbound-message retries: re-dispatch RETRYING rows whose next_retry_at has passed.
# Every minute — the first ladder rung defaults to 60s, so a slower sweep would stretch it.
scheduler.add_job(check_message_retries, "interval", minutes=1, id="message_retry_check")


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
