"""Analytics service — S53."""
from __future__ import annotations

from kink import inject

from main.app.domain.admin_config.service import AdminConfigService
from main.app.domain.analytics.models import (
    AnalyticsDashboardDto,
    MissionControlDto,
    RegionalPerformanceDto,
)
from main.app.domain.analytics.repo import AnalyticsRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AnalyticsService:
    def __init__(self, repo: AnalyticsRepo, config_svc: AdminConfigService):
        self._repo = repo
        self._config_svc = config_svc

    async def get_mission_control(self) -> MissionControlDto:
        stuck_hours = await self._config_svc.get_int("task_sla_hours", 48)
        return await self._repo.mission_control(stuck_threshold_hours=stuck_hours)

    async def get_regional_performance(self) -> RegionalPerformanceDto:
        return await self._repo.regional_performance()

    async def get_analytics_dashboard(self) -> AnalyticsDashboardDto:
        funnel, avg_time, trends, revenue, dispute = await _gather(
            self._repo.conversion_funnel(),
            self._repo.avg_verification_time_by_tier(),
            self._repo.agent_performance_trends(),
            self._repo.revenue_by_location(),
            self._repo.dispute_rate(),
        )
        return AnalyticsDashboardDto(
            conversion_funnel=funnel,
            avg_time_by_tier=avg_time,
            agent_performance_trends=trends,
            revenue_by_location=revenue,
            dispute_rate=dispute,
        )


async def _gather(*coros):
    import asyncio
    return await asyncio.gather(*coros)
