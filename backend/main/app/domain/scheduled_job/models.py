"""When each scheduled job last ran — the clock every sweep runner shares (D12 follow-up).

Two runners call the same tick over `JOB_REGISTRY` (`app/jobs/registry.py`): the Cloudflare
Cron Worker, through `POST /internal/sweeps/tick`, on the deployed serverless environments; and
the in-process scheduler on local and long-running hosts. Neither keeps time itself. A job runs
when its trigger's next fire time after its row's anchor has passed — `last_run_at`, or, for a
job never run, the row's `date_created` — and whichever runner claims the row first runs it.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


class JobClaim(str, enum.Enum):
    """What a runner learned when it asked to run a job."""

    CLAIMED = "CLAIMED"                        # due, and this runner now owns this fire
    NOT_DUE = "NOT_DUE"                        # its next fire time has not come yet
    CLAIMED_ELSEWHERE = "CLAIMED_ELSEWHERE"    # due, but a concurrent runner claimed it first


class SweepJobOutcome(str, enum.Enum):
    """What one tick did with one job."""

    RAN = "RAN"
    FAILED = "FAILED"                          # it raised; logged under the request reference
    NOT_DUE = "NOT_DUE"
    CLAIMED_ELSEWHERE = "CLAIMED_ELSEWHERE"
    DEFERRED = "DEFERRED"                      # the tick's time budget ran out first; still due


# ─── ORM ──────────────────────────────────────────────────────────

class ScheduledJobRun(BaseEntity):
    __tablename__ = "scheduled_job_runs"

    # The registry's job name; one row per job, created the first time a tick sees it.
    name = Column(String(64), nullable=False, unique=True, index=True)
    # When the last claimed run started. None until the job first runs.
    last_run_at = Column(UTCDateTime, nullable=True)
    # Set when that run raised: the job is due again from here, sooner than its next fire time.
    retry_at = Column(UTCDateTime, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateScheduledJobRunDto(Object):
    name: str


class UpdateScheduledJobRunDto(Object):
    pass


class SearchScheduledJobRunDto(InternalPageRequest, BaseQueryDto):
    name: Optional[str] = None


class QueryScheduledJobRunDto(BaseQueryDto):
    name: Optional[str] = None
    last_run_at: Optional[datetime] = None


class SweepJobResultDto(Object):
    name: str
    outcome: SweepJobOutcome
    duration_ms: Optional[int] = None          # set for a job this tick ran


class SweepTickResultDto(Object):
    """One tick's summary, in registry order — what the Worker logs."""

    jobs: List[SweepJobResultDto]
