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
from main.app.domain.broadcast.service import BroadcastService
from main.app.domain.earnings.service import EarningsService
from main.app.domain.referral.service import ReferralService
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.service import VerificationTaskService
from main.app.domain.verification.sla_monitor import SlaMonitorService
from main.appodus_utils.integrations.messaging.service import MessagingService
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


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class SlaMonitorJobs:
    """Fresh-session wrapper around the SLA-breach sweep (§12.2, D23)."""

    def __init__(self, sla_monitor: SlaMonitorService):
        self._sla_monitor = sla_monitor

    async def run_sla_breach_sweep(self) -> int:
        return await self._sla_monitor.sweep_sla_breaches()


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class EarningsSweepJobs:
    """Fresh-session wrapper around the commission clearance/reserve sweep (§15.2, S19)."""

    def __init__(self, earnings_service: EarningsService):
        self._earnings = earnings_service

    async def run_commission_clearance_sweep(self) -> int:
        return await self._earnings.sweep_cleared()


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class GrowthSweepJobs:
    """Fresh-session wrappers around the §17.1 growth sweeps — abandoned-draft recovery
    (one email per abandoned draft) + referral-credit clearance (S21)."""

    def __init__(self, verification_service: VerificationService, referral_service: ReferralService):
        self._verification = verification_service
        self._referral = referral_service

    async def run_abandonment_sweep(self) -> int:
        return await self._verification.sweep_abandoned_drafts()

    async def run_referral_credit_sweep(self) -> int:
        return await self._referral.sweep_referral_credits()


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class BroadcastSweepJobs:
    """Fresh-session wrapper around the scheduled-broadcast send sweep (§18.1, S22)."""

    def __init__(self, broadcast_service: BroadcastService):
        self._broadcast = broadcast_service

    async def run_scheduled_broadcast_sweep(self) -> int:
        return await self._broadcast.sweep_scheduled_broadcasts()


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


async def check_sla_breaches() -> None:
    flagged = await di[SlaMonitorJobs].run_sla_breach_sweep()
    if flagged:
        logger.info("SLA-breach sweep flagged {} verification(s)", flagged)


async def check_commission_clearance() -> None:
    advanced = await di[EarningsSweepJobs].run_commission_clearance_sweep()
    if advanced:
        logger.info("commission clearance sweep advanced {} commission(s)", advanced)


async def check_task_no_show_timeouts() -> None:
    reclaimed = await di[TaskSweepJobs].run_no_show_sweep()
    if reclaimed:
        logger.info("no-show sweep reclaimed {} task(s)", reclaimed)


async def check_task_pool_timeouts() -> None:
    escalated = await di[TaskSweepJobs].run_pool_starvation_sweep()
    if escalated:
        logger.info("pool-starvation sweep escalated {} task(s)", escalated)


async def check_abandoned_drafts() -> None:
    reminded = await di[GrowthSweepJobs].run_abandonment_sweep()
    if reminded:
        logger.info("abandonment sweep reminded {} draft(s)", reminded)


async def check_referral_credits() -> None:
    cleared = await di[GrowthSweepJobs].run_referral_credit_sweep()
    if cleared:
        logger.info("referral-credit sweep cleared {} credit(s)", cleared)


async def check_scheduled_broadcasts() -> None:
    sent = await di[BroadcastSweepJobs].run_scheduled_broadcast_sweep()
    if sent:
        logger.info("broadcast sweep sent {} scheduled broadcast(s)", sent)


async def check_message_retries() -> None:
    stats = await di[MessageRetrySweepJobs].run_message_retry_sweep()
    if any(stats.values()):
        logger.info("message-retry sweep: {}", stats)


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
