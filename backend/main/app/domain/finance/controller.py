"""Finance summary controller (PRD §18.1).

URL shape: /admin/finance/summary — RBAC-gated (VIEW_ADMIN_PANEL). The composition lives in
FinanceService; the detailed payouts panel (approve/hold/adjust) lives in the payout admin
controller, and the payments list in the payment admin controller.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.finance.models import FinanceSummaryDto
from main.app.domain.finance.service import FinanceService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

finance_router = APIRouter(prefix="/admin/finance", tags=["Admin: Finance"])
finance_service: FinanceService = di[FinanceService]


@finance_router.get("/summary", response_model=SuccessResponse[FinanceSummaryDto])
async def get_finance_summary(_admin_id: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL))):
    return SuccessResponse[FinanceSummaryDto](data=await finance_service.summary())
