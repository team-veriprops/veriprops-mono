"""Daily payout disbursement (PRD §15.1).

Sends approved payouts as bank transfers and settles transfers left in flight — the same
batch finance's "disburse" button runs (`PayoutDisbursementService.run`). Each payout claims
and settles in its own transaction, so this wrapper's transaction holds only the job lock.
Cadence is registered in ``app/jobs/scheduled.py``; disabled under test.

Every environment is serverless today, where this cannot run on its own clock: the button is
the reliable path until the Docker move, and this sweep is the backstop after it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.domain.payout.disbursement import PayoutDisbursementService
from main.app.domain.payout.models import DisbursementOutcomeDto
from main.app.jobs.exclusive import exclusive_job
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class PayoutSweepJobs:
    """Fresh-session wrapper around the payout disbursement batch (§15.1)."""

    def __init__(self, disbursement_service: PayoutDisbursementService):
        self._disbursement = disbursement_service

    @exclusive_job("payout_disbursement")
    async def run_payout_disbursement(self) -> Optional[DisbursementOutcomeDto]:
        return await self._disbursement.run()


async def check_payout_disbursement() -> None:
    outcome = await di[PayoutSweepJobs].run_payout_disbursement()
    if outcome and (outcome.paid or outcome.failed or outcome.in_flight):
        logger.info(
            "payout disbursement: {} paid, {} failed, {} in flight, {} still approved",
            outcome.paid, outcome.failed, outcome.in_flight, outcome.remaining,
        )
