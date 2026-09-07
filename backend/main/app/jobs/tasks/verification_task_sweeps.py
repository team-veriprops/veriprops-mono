"""Verification-task timeout sweeps (PRD §11.4, decision-log D12).

Two time-driven sweeps over the task pool: no-show reclaim (accepted tasks whose
agent never showed up are returned to the pool) and broadcast-pool starvation
escalation (tasks nobody accepted are escalated). The pure, tested logic lives on
``VerificationTaskService``; this module wraps it in ``ALWAYS_NEW`` transactional
jobs (a fresh session per sweep, outside any request lifecycle). Sweeps are
claim-based and idempotent, so they are safe to run concurrently with request
traffic. Cadence is registered in ``app/jobs/scheduled.py``; the scheduler is
disabled under test — tests invoke the sweep methods (or the admin dev sweep
endpoint) directly for determinism.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


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


async def check_task_no_show_timeouts() -> None:
    reclaimed = await di[TaskSweepJobs].run_no_show_sweep()
    if reclaimed:
        logger.info("no-show sweep reclaimed {} task(s)", reclaimed)


async def check_task_pool_timeouts() -> None:
    escalated = await di[TaskSweepJobs].run_pool_starvation_sweep()
    if escalated:
        logger.info("pool-starvation sweep escalated {} task(s)", escalated)
