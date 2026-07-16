"""Commission clearance/reserve sweep (PRD §15.2, decision-log S19).

Advances agent commissions through their clearance window (pending → cleared →
reserve release). The sweep logic lives on ``EarningsService``; this module wraps
it in an ``ALWAYS_NEW`` transactional job (fresh session per sweep, idempotent).
Cadence is registered in ``app/jobs/scheduled.py``; disabled under test — tests
call ``sweep_cleared`` directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.earnings.service import EarningsService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


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


async def check_commission_clearance() -> None:
    advanced = await di[EarningsSweepJobs].run_commission_clearance_sweep()
    if advanced:
        logger.info("commission clearance sweep advanced {} commission(s)", advanced)
