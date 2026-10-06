"""ScheduledJobRunService.claim_if_due — whether this tick runs a job, decided once.

A job is due when its trigger's next fire time after its anchor has passed. The anchor is the
last run, or, for a job never run, the moment its row was first written: a newly registered
job waits one interval (or for its next time of day) exactly as the in-process scheduler
would, rather than firing the daily payout batch at whatever hour a deploy happened.

The claim is a compare-and-set on `last_run_at`, committed on its own before the job runs, so
two clocks ticking together (the Worker and a scheduler, or two scheduler workers) run each
fire once: the loser sees the row already moved and stands down.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.scheduled_job.models import JobClaim
from main.app.domain.scheduled_job.service import ScheduledJobRunService
from main.app.jobs.registry import ScheduledJob
from main.appodus_utils import Utils

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
pytestmark = pytest.mark.usefixtures("independent_sessions")


async def _noop() -> None:
    return None


def _every(minutes: int) -> ScheduledJob:
    return ScheduledJob(name="job", run=_noop, trigger=IntervalTrigger(minutes=minutes))


def _service(row, *, wins: bool = True):
    svc = object.__new__(ScheduledJobRunService)
    repo = MagicMock()
    repo.insert_or_get = AsyncMock(return_value=(row, False))
    repo.claim_run = AsyncMock(return_value=wins)
    svc._scheduled_job_run_repo = repo
    return svc, repo


def _row(*, last_run_at=None, date_created=NOW - timedelta(days=1)):
    return SimpleNamespace(name="job", last_run_at=last_run_at, date_created=date_created)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(Utils, "datetime_now", staticmethod(lambda: NOW))


async def test_the_row_is_created_on_first_sight_and_keyed_by_name():
    svc, repo = _service(_row())

    await svc.claim_if_due(_every(1))

    repo.insert_or_get.assert_awaited_once_with({"name": "job"}, ["name"])


async def test_a_job_never_run_waits_one_interval_from_when_it_was_first_seen():
    svc, repo = _service(_row(date_created=NOW - timedelta(seconds=30)))

    assert await svc.claim_if_due(_every(1)) == JobClaim.NOT_DUE
    repo.claim_run.assert_not_awaited()


async def test_a_job_never_run_is_due_once_that_interval_has_passed():
    svc, repo = _service(_row(date_created=NOW - timedelta(minutes=1)))

    assert await svc.claim_if_due(_every(1)) == JobClaim.CLAIMED
    repo.claim_run.assert_awaited_once_with("job", expected_last_run_at=None, at=NOW)


async def test_a_job_run_recently_is_not_due():
    svc, repo = _service(_row(last_run_at=NOW - timedelta(minutes=4)))

    assert await svc.claim_if_due(_every(5)) == JobClaim.NOT_DUE
    repo.claim_run.assert_not_awaited()


async def test_a_due_job_is_claimed_against_the_last_run_it_was_judged_on():
    last = NOW - timedelta(minutes=5)
    svc, repo = _service(_row(last_run_at=last))

    assert await svc.claim_if_due(_every(5)) == JobClaim.CLAIMED
    repo.claim_run.assert_awaited_once_with("job", expected_last_run_at=last, at=NOW)


async def test_losing_the_claim_to_a_concurrent_tick_stands_down():
    svc, _ = _service(_row(last_run_at=NOW - timedelta(hours=1)), wins=False)

    assert await svc.claim_if_due(_every(5)) == JobClaim.CLAIMED_ELSEWHERE


async def test_a_daily_job_first_seen_after_its_time_waits_for_the_next_day():
    # Deployed at 13:00 Lagos: the 10:00 batch must not run off-schedule right away.
    daily = ScheduledJob(name="job", run=_noop, trigger=CronTrigger(hour=10, minute=0, timezone="Africa/Lagos"))
    svc, repo = _service(_row(date_created=NOW - timedelta(minutes=1)))  # NOW is 13:00 Lagos

    assert await svc.claim_if_due(daily) == JobClaim.NOT_DUE
    repo.claim_run.assert_not_awaited()


async def test_the_claim_commits_in_its_own_transaction(independent_sessions):
    svc, _ = _service(_row(last_run_at=NOW - timedelta(hours=1)))

    await svc.claim_if_due(_every(5))

    assert len(independent_sessions) == 1
