"""Finance summary (PRD §18.1): collected revenue and the payment / commission / payout
counts behind the Finance landing tiles. Read-only composition over the three money repos;
the payouts panel (approve/hold/adjust/disburse) lives in the payout domain."""
from __future__ import annotations

from kink import inject

from main.app.domain.commission.repo import CommissionRepo
from main.app.domain.finance.models import FinanceSummaryDto
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.payout.models import PayoutStatus
from main.app.domain.payout.repo import PayoutRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
class FinanceService:
    def __init__(self, payment_repo: PaymentRepo, commission_repo: CommissionRepo, payout_repo: PayoutRepo):
        self._payments = payment_repo
        self._commissions = commission_repo
        self._payouts = payout_repo

    async def summary(self) -> FinanceSummaryDto:
        payouts_by_status = await self._payouts.count_by_status()
        return FinanceSummaryDto(
            revenue_minor=await self._payments.sum_collected_revenue(),
            payments_by_status=await self._payments.count_by_status(),
            commissions_by_status=await self._commissions.count_by_status(),
            payouts_by_status=payouts_by_status,
            # Requested and still waiting on finance: the "pending" chip on the landing page.
            pending_payouts=payouts_by_status.get(PayoutStatus.REQUESTED.value, 0),
        )
