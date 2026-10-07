"""The broadcast fan-out job (§18.1): one page per transaction, a bounded number per run.

Each page commits on its own, so a run that dies part-way keeps every page it finished and the
next run resumes from the cursor. The entrypoint keeps taking pages while one makes progress,
up to `BROADCAST_FANOUT_MAX_PAGES_PER_RUN`, so one huge audience cannot hold the tick.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

import main.appodus_utils.decorators.transactional as transactional_mod
from main.app.config.settings import settings
from main.app.jobs import exclusive as exclusive_mod
from main.app.jobs.tasks import broadcast_sweeps


@pytest.fixture
def job(monkeypatch):
    job = MagicMock()
    monkeypatch.setattr(broadcast_sweeps, "di", {broadcast_sweeps.BroadcastSweepJobs: job})
    monkeypatch.setattr(broadcast_sweeps, "logger", MagicMock())
    return job


async def test_pages_are_taken_while_they_make_progress(job):
    job.run_fanout_page = AsyncMock(side_effect=[True, True, False])

    await broadcast_sweeps.check_broadcast_fanout()

    assert job.run_fanout_page.await_count == 3


async def test_a_run_takes_at_most_the_page_cap(job, monkeypatch):
    monkeypatch.setattr(settings, "BROADCAST_FANOUT_MAX_PAGES_PER_RUN", 4)
    job.run_fanout_page = AsyncMock(return_value=True)

    await broadcast_sweeps.check_broadcast_fanout()

    assert job.run_fanout_page.await_count == 4


async def test_another_worker_holding_the_job_ends_the_run(job):
    job.run_fanout_page = AsyncMock(return_value=None)

    await broadcast_sweeps.check_broadcast_fanout()

    assert job.run_fanout_page.await_count == 1


async def test_each_page_runs_in_its_own_transaction_under_the_job_lock(monkeypatch):
    sessions, locks = [], []

    @asynccontextmanager
    async def _fake_new_session(independent: bool = False):
        session = MagicMock()
        session.in_transaction.return_value = True
        sessions.append(session)
        yield session

    async def _try_lock(name):
        locks.append(name)
        return True

    monkeypatch.setattr(transactional_mod, "create_new_db_session", _fake_new_session)
    monkeypatch.setattr(exclusive_mod, "try_advisory_xact_lock", _try_lock)
    wrapper = object.__new__(broadcast_sweeps.BroadcastSweepJobs)
    wrapper._broadcast = MagicMock(fanout_next_page=AsyncMock(return_value=True))

    assert await wrapper.run_fanout_page() is True
    assert await wrapper.run_fanout_page() is True

    assert len(sessions) == 2
    assert locks == ["job:broadcast_fanout", "job:broadcast_fanout"]
