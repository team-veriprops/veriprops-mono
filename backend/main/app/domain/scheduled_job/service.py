"""Claims a scheduled job's next fire for one runner (D12 follow-up)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import inject

from main.app.domain.scheduled_job.models import JobClaim
from main.app.domain.scheduled_job.repo import ScheduledJobRunRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional

if TYPE_CHECKING:
    from main.app.jobs.registry import ScheduledJob


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.INDEPENDENT),
    exclude=["__init__"], exclude_startswith=["_"],
)
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ScheduledJobRunService:
    """Decides, once per fire, which runner runs a job.

    The claim commits in its **own** transaction before the job starts, so a concurrent tick
    sees the row already moved and stands down instead of running the same fire again. The
    job's `exclusive_job` lock only stops two runs overlapping; this stops them repeating.
    A job that fails after its claim waits for its next fire time, like a scheduler would.
    """

    def __init__(self, scheduled_job_run_repo: ScheduledJobRunRepo):
        self._scheduled_job_run_repo = scheduled_job_run_repo

    async def claim_if_due(self, job: ScheduledJob) -> JobClaim:
        now = Utils.datetime_now()
        row, _ = await self._scheduled_job_run_repo.insert_or_get({"name": job.name}, ["name"])
        # A job never run is anchored where it was first seen: a new job waits one interval
        # (or for its time of day), rather than firing the moment it is deployed.
        anchor = row.last_run_at or row.date_created
        next_fire = job.next_fire_after(anchor)
        if next_fire is None or next_fire > now:
            return JobClaim.NOT_DUE
        won = await self._scheduled_job_run_repo.claim_run(
            job.name, expected_last_run_at=row.last_run_at, at=now,
        )
        return JobClaim.CLAIMED if won else JobClaim.CLAIMED_ELSEWHERE
