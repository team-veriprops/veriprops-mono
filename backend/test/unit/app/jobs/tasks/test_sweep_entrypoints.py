"""Sweep task modules (app/jobs/tasks/*): each scheduler entrypoint resolves its
job wrapper from DI and awaits the right sweep method, logging only when the
sweep did work; each job wrapper is a pure delegation to its domain service."""
from contextlib import asynccontextmanager
from typing import NamedTuple

import pytest
from unittest.mock import AsyncMock, MagicMock

import main.appodus_utils.decorators.transactional as transactional_mod
from main.app.jobs.tasks import (
    broadcast_sweeps,
    earnings_sweeps,
    growth_sweeps,
    message_retry_sweeps,
    sla_sweeps,
    verification_task_sweeps,
)


class SweepCase(NamedTuple):
    module: object
    entrypoint: str
    job_cls: type
    job_method: str
    service_attr: str
    service_method: str
    busy_result: object  # sweep found work -> entrypoint logs
    idle_result: object  # sweep found nothing -> entrypoint stays silent


CASES = [
    pytest.param(
        SweepCase(verification_task_sweeps, "check_task_no_show_timeouts",
                  verification_task_sweeps.TaskSweepJobs, "run_no_show_sweep",
                  "_task_service", "sweep_no_show", 2, 0),
        id="no_show",
    ),
    pytest.param(
        SweepCase(verification_task_sweeps, "check_task_pool_timeouts",
                  verification_task_sweeps.TaskSweepJobs, "run_pool_starvation_sweep",
                  "_task_service", "sweep_pool_starvation", 1, 0),
        id="pool_starvation",
    ),
    pytest.param(
        SweepCase(sla_sweeps, "check_sla_breaches",
                  sla_sweeps.SlaMonitorJobs, "run_sla_breach_sweep",
                  "_sla_monitor", "sweep_sla_breaches", 3, 0),
        id="sla_breach",
    ),
    pytest.param(
        SweepCase(earnings_sweeps, "check_commission_clearance",
                  earnings_sweeps.EarningsSweepJobs, "run_commission_clearance_sweep",
                  "_earnings", "sweep_cleared", 4, 0),
        id="commission_clearance",
    ),
    pytest.param(
        SweepCase(growth_sweeps, "check_abandoned_drafts",
                  growth_sweeps.GrowthSweepJobs, "run_abandonment_sweep",
                  "_verification", "sweep_abandoned_drafts", 1, 0),
        id="abandonment",
    ),
    pytest.param(
        SweepCase(growth_sweeps, "check_referral_credits",
                  growth_sweeps.GrowthSweepJobs, "run_referral_credit_sweep",
                  "_referral", "sweep_referral_credits", 2, 0),
        id="referral_credit",
    ),
    pytest.param(
        SweepCase(broadcast_sweeps, "check_scheduled_broadcasts",
                  broadcast_sweeps.BroadcastSweepJobs, "run_scheduled_broadcast_sweep",
                  "_broadcast", "sweep_scheduled_broadcasts", 1, 0),
        id="scheduled_broadcast",
    ),
    pytest.param(
        SweepCase(message_retry_sweeps, "check_message_retries",
                  message_retry_sweeps.MessageRetrySweepJobs, "run_message_retry_sweep",
                  "_messaging_service", "process_retries",
                  {"dispatched": 2, "failed": 0}, {"dispatched": 0, "failed": 0}),
        id="message_retry",
    ),
]


def _seed_job(monkeypatch, case: SweepCase, result):
    """Point the task module's `di[JobClass]` lookup at a mocked job wrapper."""
    job = MagicMock()
    setattr(job, case.job_method, AsyncMock(return_value=result))
    monkeypatch.setattr(case.module, "di", {case.job_cls: job})
    fake_logger = MagicMock()
    monkeypatch.setattr(case.module, "logger", fake_logger)
    return job, fake_logger


@pytest.mark.parametrize("case", CASES)
async def test_entrypoint_awaits_job_and_logs_when_sweep_did_work(monkeypatch, case):
    job, fake_logger = _seed_job(monkeypatch, case, case.busy_result)

    await getattr(case.module, case.entrypoint)()

    getattr(job, case.job_method).assert_awaited_once_with()
    fake_logger.info.assert_called_once()


@pytest.mark.parametrize("case", CASES)
async def test_entrypoint_stays_silent_when_sweep_found_nothing(monkeypatch, case):
    job, fake_logger = _seed_job(monkeypatch, case, case.idle_result)

    await getattr(case.module, case.entrypoint)()

    getattr(job, case.job_method).assert_awaited_once_with()
    fake_logger.info.assert_not_called()


@pytest.mark.parametrize("case", CASES)
async def test_job_wrapper_delegates_to_domain_service(monkeypatch, case):
    # ALWAYS_NEW would open a real session; hand the wrapper a fake one that is
    # already "in a transaction" so `execute` just awaits the wrapped method.
    @asynccontextmanager
    async def _fake_new_session():
        session = MagicMock()
        session.in_transaction.return_value = True
        yield session

    monkeypatch.setattr(transactional_mod, "create_new_db_session", _fake_new_session)

    job = object.__new__(case.job_cls)
    service = MagicMock()
    setattr(service, case.service_method, AsyncMock(return_value=case.busy_result))
    setattr(job, case.service_attr, service)

    result = await getattr(job, case.job_method)()

    assert result == case.busy_result
    getattr(service, case.service_method).assert_awaited_once_with()
