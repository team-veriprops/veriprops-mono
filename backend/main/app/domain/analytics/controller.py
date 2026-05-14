"""Analytics controller — S53."""
from __future__ import annotations

from fastapi import Depends
from kink import di

from main.app.domain.analytics.models import (
    AnalyticsDashboardDto,
    MissionControlDto,
    RegionalPerformanceDto,
)
from main.app.domain.analytics.service import AnalyticsService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

analytics_router = AppRouter(prefix="/admin/analytics", tags=["Analytics"])

_auth = AuthJWTBearer(required_permissions=["VIEW_ADMIN_PANEL"])


@analytics_router.get("/mission-control", response_model=SuccessResponse[MissionControlDto])
async def get_mission_control(_: JWTClaims = Depends(_auth)):
    svc: AnalyticsService = di[AnalyticsService]
    data = await svc.get_mission_control()
    return SuccessResponse.ok(data)


@analytics_router.get("/regional-performance", response_model=SuccessResponse[RegionalPerformanceDto])
async def get_regional_performance(_: JWTClaims = Depends(_auth)):
    svc: AnalyticsService = di[AnalyticsService]
    data = await svc.get_regional_performance()
    return SuccessResponse.ok(data)


@analytics_router.get("/dashboard", response_model=SuccessResponse[AnalyticsDashboardDto])
async def get_analytics_dashboard(_: JWTClaims = Depends(_auth)):
    svc: AnalyticsService = di[AnalyticsService]
    data = await svc.get_analytics_dashboard()
    return SuccessResponse.ok(data)
