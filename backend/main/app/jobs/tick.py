"""One sweep tick: run every job in the registry that is due (D12 follow-up).

Both runners call this — the Cloudflare Cron Worker through `POST /internal/sweeps/tick`, and
the in-process scheduler every minute — so whether a job runs is decided by its claim on
`scheduled_job_runs` (`ScheduledJobRunService.claim_if_due`), never by which runner fired.

Jobs run one after another in registry order, each in its own transaction under its own
`exclusive_job` lock. A job that raises is logged, reported, and made due again after
`SCHEDULED_JOB_RETRY_SECONDS`; the tick moves on. Once the
time budget is spent the tick starts nothing more: the remaining jobs keep their claims for the
next tick, which keeps a slow run inside the serverless function's time limit.
"""
from __future__ import annotations

import time
from typing import List, Optional, Sequence

from kink import di

from main.app.config.settings import settings
from main.app.domain.scheduled_job.models import JobClaim, SweepJobOutcome, SweepJobResultDto, SweepTickResultDto
from main.app.domain.scheduled_job.service import ScheduledJobRunService
from main.app.jobs.registry import JOB_REGISTRY, ScheduledJob
from main.appodus_utils.exception.faults import log_fault_once

_UNCLAIMED_OUTCOME = {
    JobClaim.NOT_DUE: SweepJobOutcome.NOT_DUE,
    JobClaim.CLAIMED_ELSEWHERE: SweepJobOutcome.CLAIMED_ELSEWHERE,
}


async def _run(job: ScheduledJob) -> SweepJobResultDto:
    started = time.monotonic()
    try:
        await job.run()
        outcome = SweepJobOutcome.RAN
    except Exception as exc:
        log_fault_once(exc, f"sweep {job.name}")
        outcome = SweepJobOutcome.FAILED
    return SweepJobResultDto(
        name=job.name, outcome=outcome, duration_ms=int((time.monotonic() - started) * 1000),
    )


async def run_sweep_tick(
    *,
    registry: Sequence[ScheduledJob] = JOB_REGISTRY,
    budget_seconds: Optional[float] = None,
) -> SweepTickResultDto:
    budget = settings.SWEEP_TICK_BUDGET_SECONDS if budget_seconds is None else budget_seconds
    claims = di[ScheduledJobRunService]
    started = time.monotonic()
    results: List[SweepJobResultDto] = []
    for job in registry:
        if time.monotonic() - started >= budget:
            results.append(SweepJobResultDto(name=job.name, outcome=SweepJobOutcome.DEFERRED))
            continue
        claim = await claims.claim_if_due(job)
        if claim != JobClaim.CLAIMED:
            results.append(SweepJobResultDto(name=job.name, outcome=_UNCLAIMED_OUTCOME[claim]))
            continue
        result = await _run(job)
        if result.outcome == SweepJobOutcome.FAILED:
            await claims.record_failure(job)
        results.append(result)
    return SweepTickResultDto(jobs=results)
