"""Analytics admin controller (PRD §18.1, D38).

URL shape: /admin/analytics — RBAC-gated (VIEW_ANALYTICS). Every figure is backend-derived.
Frontend service: frontend/src/components/admin/analytics/libs/analytics-service.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.analytics.models import (
    AgentTrendsDto,
    FunnelDto,
    RegionalRowDto,
    RevenueDto,
    TierTimeDto,
)
from main.app.domain.analytics.service import AnalyticsService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

analytics_router = APIRouter(prefix="/admin/analytics", tags=["Admin: Analytics"])
analytics_service: AnalyticsService = di[AnalyticsService]
_guard = require_permission(Permission.VIEW_ANALYTICS)


@analytics_router.get("/funnel", response_model=SuccessResponse[FunnelDto])
async def get_funnel(_admin_id: str = Depends(_guard)):
    return SuccessResponse[FunnelDto](data=await analytics_service.funnel())


@analytics_router.get("/time-by-tier", response_model=SuccessResponse[List[TierTimeDto]])
async def get_time_by_tier(_admin_id: str = Depends(_guard)):
    return SuccessResponse[List[TierTimeDto]](data=await analytics_service.time_by_tier())


@analytics_router.get("/revenue", response_model=SuccessResponse[RevenueDto])
async def get_revenue(_admin_id: str = Depends(_guard)):
    return SuccessResponse[RevenueDto](data=await analytics_service.revenue())


@analytics_router.get("/regional", response_model=SuccessResponse[List[RegionalRowDto]])
async def get_regional(_admin_id: str = Depends(_guard)):
    return SuccessResponse[List[RegionalRowDto]](data=await analytics_service.regional())


@analytics_router.get("/agent-trends", response_model=SuccessResponse[AgentTrendsDto])
async def get_agent_trends(_admin_id: str = Depends(_guard)):
    return SuccessResponse[AgentTrendsDto](data=await analytics_service.agent_trends())
