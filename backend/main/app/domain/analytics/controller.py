"""Analytics admin controller (PRD §18.1, D38).

URL shape: /admin/analytics — RBAC-gated (VIEW_ANALYTICS). Every figure is backend-derived.
Frontend service: frontend/src/components/admin/analytics/libs/analytics-service.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.analytics.models import (
    AgentTrendsDto,
    FunnelDto,
    RegionalRowDto,
    RevenueDto,
    TierTimeDto,
    WhatsAppChannelAnalyticsDto,
)
from main.app.domain.analytics.service import AnalyticsService
from main.app.domain.channel.whatsapp.analytics.health_service import (
    WhatsAppNumberHealthService,
)
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

analytics_router = APIRouter(prefix="/admin/analytics", tags=["Admin: Analytics"])
analytics_service: AnalyticsService = di[AnalyticsService]
number_health_service: WhatsAppNumberHealthService = di[WhatsAppNumberHealthService]
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


@analytics_router.get(
    "/whatsapp",
    response_model=SuccessResponse[WhatsAppChannelAnalyticsDto],
    summary="The seven §26.10 WhatsApp channel metrics over a trailing window",
)
async def get_whatsapp_channel(
    # A loose Query param rather than a DTO, matching the audit controller — the only
    # other date-filtered admin surface. Omitted means the configured default window.
    days: Optional[int] = Query(default=None, ge=1, le=365),
    _admin_id: str = Depends(_guard),
):
    return SuccessResponse[WhatsAppChannelAnalyticsDto](
        data=await analytics_service.whatsapp_channel(days)
    )


@analytics_router.post(
    "/whatsapp/quality/sync",
    response_model=SuccessResponse[WhatsAppChannelAnalyticsDto],
    summary="Re-read Meta's quality rating for the business number (§26.10, D81)",
)
async def sync_whatsapp_quality(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    # A heavier permission than reading: this reaches an external API on demand, which is
    # the same reason the §26.7 template sync is CONFIGURE_SYSTEM rather than VIEW_ANALYTICS.
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Sync, then return the whole panel so the page re-renders from one response.

    The sync itself never raises — a failed Graph call is recorded on the row and shown as
    a sync age, because a dashboard tile is not worth a 500.
    """
    await number_health_service.sync()
    return SuccessResponse[WhatsAppChannelAnalyticsDto](
        data=await analytics_service.whatsapp_channel(days)
    )
