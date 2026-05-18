"""Portal dashboard summary endpoint."""
from __future__ import annotations

from fastapi import Depends

from main.app.domain.verification.portal.dashboard_service import PortalDashboardService
from main.app.domain.verification.portal.models import DashboardSummaryDto
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

portal_dashboard_router = AppRouter(prefix="/portal/dashboard", tags=["Portal — Dashboard"])

_auth = AuthJWTBearer()


@portal_dashboard_router.get("/summary", response_model=SuccessResponse[DashboardSummaryDto])
async def get_dashboard_summary(
    svc: PortalDashboardService = Depends(lambda: di[PortalDashboardService]),
    claims=Depends(_auth),
):
    result = await svc.get_summary(customer_id=claims.sub)
    return SuccessResponse.ok(result)
