"""Growth sweeps (PRD §17.1, decision-log S21).

Two conversion/retention sweeps: abandoned-draft recovery (one reminder email per
abandoned verification draft) and referral-credit clearance (matures pending
referral credits into spendable ones). The sweep logic lives on
``VerificationService`` / ``ReferralService``; this module wraps both in
``ALWAYS_NEW`` transactional jobs (fresh session per sweep, idempotent). Cadence
is registered in ``app/jobs/scheduled.py``; disabled under test — tests call the
sweep methods directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.referral.service import ReferralService
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class GrowthSweepJobs:
    """Fresh-session wrappers around the §17.1 growth sweeps — abandoned-draft recovery
    (one email per abandoned draft) + referral-credit clearance (S21)."""

    def __init__(self, verification_service: VerificationService, referral_service: ReferralService):
        self._verification = verification_service
        self._referral = referral_service

    async def run_abandonment_sweep(self) -> int:
        return await self._verification.sweep_abandoned_drafts()

    async def run_referral_credit_sweep(self) -> int:
        return await self._referral.sweep_referral_credits()


async def check_abandoned_drafts() -> None:
    reminded = await di[GrowthSweepJobs].run_abandonment_sweep()
    if reminded:
        logger.info("abandonment sweep reminded {} draft(s)", reminded)


async def check_referral_credits() -> None:
    cleared = await di[GrowthSweepJobs].run_referral_credit_sweep()
    if cleared:
        logger.info("referral-credit sweep cleared {} credit(s)", cleared)
