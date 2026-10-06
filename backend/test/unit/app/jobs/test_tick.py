"""The sweep tick (app/jobs/tick.py): one pass over the job registry.

Both clocks call it — the Cloudflare Cron Worker through `POST /internal/sweeps/tick`, and
the in-process scheduler — so whether a job runs is decided by the claim on its
`scheduled_job_runs` row, never by which clock fired. The tick runs each claimed job in
registry order, keeps going past a failure, and stops starting jobs once its time budget is
spent, leaving the rest due for the next tick.
"""
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from main.app.domain.scheduled_job.models import JobClaim, SweepJobOutcome
from main.app.domain.scheduled_job.service import ScheduledJobRunService
from main.app.jobs import tick as tick_mod
from main.app.jobs.registry import ScheduledJob
from test.utils.di_override import override_service

from apscheduler.triggers.interval import IntervalTrigger


class FakeClaims:
    """Answers each job's claim from a table; records what was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked: List[str] = []

    async def claim_if_due(self, job: ScheduledJob) -> JobClaim:
        self.asked.append(job.name)
        return self.answers.get(job.name, JobClaim.CLAIMED)


def _job(name: str, ran: List[str], *, fails: bool = False) -> ScheduledJob:
    async def run() -> None:
        ran.append(name)
        if fails:
            raise RuntimeError(f"{name} blew up")
    return ScheduledJob(name=name, run=run, trigger=IntervalTrigger(minutes=1))


@pytest.fixture
def claims(monkeypatch):
    fake = FakeClaims({})
    override_service(monkeypatch, ScheduledJobRunService, fake)
    return fake


def _outcomes(result):
    return {job.name: job.outcome for job in result.jobs}


async def test_runs_each_claimed_job_in_registry_order(claims):
    ran: List[str] = []
    claims.answers = {"b": JobClaim.NOT_DUE, "c": JobClaim.CLAIMED_ELSEWHERE}
    registry = (_job("a", ran), _job("b", ran), _job("c", ran), _job("d", ran))

    result = await tick_mod.run_sweep_tick(registry=registry)

    assert ran == ["a", "d"]
    assert _outcomes(result) == {
        "a": SweepJobOutcome.RAN,
        "b": SweepJobOutcome.NOT_DUE,
        "c": SweepJobOutcome.CLAIMED_ELSEWHERE,
        "d": SweepJobOutcome.RAN,
    }
    assert [job.name for job in result.jobs] == ["a", "b", "c", "d"]


async def test_a_failing_job_is_reported_and_the_rest_still_run(claims):
    ran: List[str] = []
    registry = (_job("a", ran, fails=True), _job("b", ran))

    result = await tick_mod.run_sweep_tick(registry=registry)

    assert ran == ["a", "b"]
    assert _outcomes(result) == {"a": SweepJobOutcome.FAILED, "b": SweepJobOutcome.RAN}


async def test_a_failure_never_carries_its_text_into_the_summary(claims):
    result = await tick_mod.run_sweep_tick(registry=(_job("a", [], fails=True),))

    assert "blew up" not in result.model_dump_json()


async def test_once_the_budget_is_spent_the_rest_are_deferred_unclaimed(claims, monkeypatch):
    ran: List[str] = []
    clock = [0.0]
    monkeypatch.setattr(tick_mod.time, "monotonic", lambda: clock[0])

    async def slow() -> None:
        ran.append("a")
        clock[0] = 50.0  # job a alone uses up the 30s budget

    registry = (ScheduledJob(name="a", run=slow, trigger=IntervalTrigger(minutes=1)),
                _job("b", ran), _job("c", ran))

    result = await tick_mod.run_sweep_tick(registry=registry, budget_seconds=30)

    assert ran == ["a"]
    assert claims.asked == ["a"]  # a deferred job keeps its claim for the next tick
    assert _outcomes(result) == {
        "a": SweepJobOutcome.RAN,
        "b": SweepJobOutcome.DEFERRED,
        "c": SweepJobOutcome.DEFERRED,
    }


async def test_the_default_budget_leaves_room_under_the_function_limit():
    # Vercel stops the function at 300s (backend/vercel.json maxDuration); a job started
    # just before the budget runs out still needs time to finish.
    from main.app.config.settings import settings
    assert 0 < settings.SWEEP_TICK_BUDGET_SECONDS <= 240


def test_the_registry_entries_are_what_the_tick_iterates_by_default():
    import inspect
    from main.app.jobs.registry import JOB_REGISTRY
    assert inspect.signature(tick_mod.run_sweep_tick).parameters["registry"].default is JOB_REGISTRY


# Keep the helper honest: a trigger built here must behave like the registry's.
def test_helper_jobs_use_a_real_trigger():
    job = _job("x", [])
    anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert job.next_fire_after(anchor) == anchor + timedelta(minutes=1)
