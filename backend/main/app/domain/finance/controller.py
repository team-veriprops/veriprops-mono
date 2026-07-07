"""Finance summary controller (PRD §18.1) — orchestration-only, no entity.

URL shape: /admin/finance/summary — RBAC-gated (VIEW_ADMIN_PANEL). Composes the payment /
commission / payout counts + collected revenue for the Finance landing tiles; the detailed
payouts panel (approve/hold/adjust) lives in the S19 payout admin controller.
"""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.commission.repo import CommissionRepo
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.payout.models import PayoutStatus
from main.app.domain.payout.repo import PayoutRepo
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils import Object
from main.appodus_utils.db.models import SuccessResponse

finance_router = APIRouter(prefix="/admin/finance", tags=["Admin: Finance"])
payment_repo: PaymentRepo = di[PaymentRepo]
commission_repo: CommissionRepo = di[CommissionRepo]
payout_repo: PayoutRepo = di[PayoutRepo]


class FinanceSummaryDto(Object):
    revenue_minor: int = 0
    payments_by_status: Dict[str, int] = {}
    commissions_by_status: Dict[str, int] = {}
    payouts_by_status: Dict[str, int] = {}
    pending_payouts: int = 0


@finance_router.get("/summary", response_model=SuccessResponse[FinanceSummaryDto])
async def get_finance_summary(_admin_id: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL))):
    payouts_by_status = await payout_repo.count_by_status()
    return SuccessResponse[FinanceSummaryDto](data=FinanceSummaryDto(
        revenue_minor=await payment_repo.sum_succeeded_amount(),
        payments_by_status=await payment_repo.count_by_status(),
        commissions_by_status=await commission_repo.count_by_status(),
        payouts_by_status=payouts_by_status,
        pending_payouts=payouts_by_status.get(PayoutStatus.REQUESTED.value, 0),
    ))
