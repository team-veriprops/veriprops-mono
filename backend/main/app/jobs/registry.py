"""Every scheduled job and its cadence, declared once (PRD §11.4 timeout sweeps, §6.4 SLA shedding).

The individual sweep tasks — job wrappers plus their ``check_*`` entrypoints — live
one-file-per-concern under ``app/jobs/tasks/``. This module names each one and gives it the
APScheduler trigger that says when it is due; all cadences are kept together so they are
visible in one place.

Nothing here runs a job. The tick (``app/jobs/tick.py``) walks this registry and runs what is
due, called by the Cloudflare Cron Worker on deployed environments and by the in-process
scheduler (``app/jobs/scheduled.py``) elsewhere. Sweeps are claim-based and idempotent, safe
alongside request traffic and the admin sweep buttons (decision-log D12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional, Tuple

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from main.app.jobs.tasks import (
    check_abandoned_drafts,
    check_commission_clearance,
    check_expired_key_values,
    check_message_retries,
    check_payout_disbursement,
    check_pending_assistant_turns,
    check_referral_credits,
    check_scheduled_broadcasts,
    check_sla_breaches,
    check_task_no_show_timeouts,
    check_task_pool_timeouts,
    check_unprocessed_whatsapp_inbound,
)


@dataclass(frozen=True)
class ScheduledJob:
    """A sweep entrypoint and the trigger that says when it is due."""

    name: str                                # `scheduled_job_runs.name`; never rename a live one
    run: Callable[[], Awaitable[None]]
    trigger: BaseTrigger

    def next_fire_after(self, anchor: datetime) -> Optional[datetime]:
        """The first fire time strictly after *anchor* (the last run, or first sight)."""
        return self.trigger.get_next_fire_time(anchor, anchor)


def _every(minutes: int) -> IntervalTrigger:
    return IntervalTrigger(minutes=minutes, timezone=timezone.utc)


JOB_REGISTRY: Tuple[ScheduledJob, ...] = (
    # Task-monitor jobs (pool timeout + no-show reclaim) and the SLA-breach sweep.
    ScheduledJob("pool_timeout_check", check_task_pool_timeouts, _every(15)),
    ScheduledJob("no_show_check", check_task_no_show_timeouts, _every(15)),
    ScheduledJob("sla_breach_check", check_sla_breaches, _every(30)),
    ScheduledJob("commission_clearance_check", check_commission_clearance, _every(60)),
    # Approved payouts leave as bank transfers once a day, mid-morning Lagos time, when banks are
    # settling (§15.1). Finance's "disburse" button runs the same batch on demand.
    ScheduledJob(
        "payout_disbursement", check_payout_disbursement,
        CronTrigger(hour=10, minute=0, timezone="Africa/Lagos"),
    ),
    # Growth sweeps (§17.1): abandonment recovery (hourly) + referral-credit clearance (daily-ish).
    ScheduledJob("abandonment_recovery_check", check_abandoned_drafts, _every(60)),
    ScheduledJob("referral_credit_check", check_referral_credits, _every(180)),
    # Scheduled admin broadcasts (§18.1): send those whose time has passed.
    ScheduledJob("scheduled_broadcast_check", check_scheduled_broadcasts, _every(5)),
    # Outbound-message retries: re-dispatch RETRYING rows whose next_retry_at has passed.
    # Every minute — the first ladder rung defaults to 60s, so a slower sweep would stretch it.
    ScheduledJob("message_retry_check", check_message_retries, _every(1)),
    # Assistant turns left pending when a customer's tab closed before asking for them (D93).
    # The backstop, not the path: the client re-issues the turn itself on reload.
    ScheduledJob("assistant_pending_turn_check", check_pending_assistant_turns, _every(1)),
    # Expired OTP codes, rate-limit windows and OAuth states left in the SQL key/value store.
    ScheduledJob("expired_key_value_cleanup", check_expired_key_values, _every(60)),
    # Inbound WhatsApp messages journalled but never surfaced (a failure after the journal write).
    # The backstop: the number's next message catches these up on its own.
    ScheduledJob("unprocessed_whatsapp_inbound_check", check_unprocessed_whatsapp_inbound, _every(5)),
)


def job_named(name: str) -> ScheduledJob:
    return next(job for job in JOB_REGISTRY if job.name == name)
