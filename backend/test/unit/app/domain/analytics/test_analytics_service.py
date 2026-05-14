"""Unit tests for AnalyticsService (S53)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.analytics.models import (
    ConversionFunnelDto,
    DisputeRateDto,
    MissionControlDto,
    RegionalPerformanceDto,
    AnalyticsDashboardDto,
    AvgVerificationTimeByTierDto,
    AgentPerformanceTrendDto,
    RevenueByLocationDto,
)
from main.app.domain.analytics.service import AnalyticsService
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_svc(repo_overrides: dict = None, config_overrides: dict = None):
    repo = MagicMock()
    config_svc = MagicMock()

    defaults = {
        "mission_control": AsyncMock(return_value=MissionControlDto(
            active_verifications=5, pending_assignments=2, stuck_jobs=1,
            sla_at_risk_count=3, revenue_total_ngn=100000.0, available_agents=8,
        )),
        "regional_performance": AsyncMock(return_value=RegionalPerformanceDto(regions=[])),
        "conversion_funnel": AsyncMock(return_value=ConversionFunnelDto(
            signups=100, submitted=80, paid=60, completed=50,
            signup_to_paid_pct=60.0, paid_to_completed_pct=83.3,
        )),
        "avg_verification_time_by_tier": AsyncMock(return_value=[]),
        "agent_performance_trends": AsyncMock(return_value=[]),
        "revenue_by_location": AsyncMock(return_value=[]),
        "dispute_rate": AsyncMock(return_value=DisputeRateDto(
            total_completed=50, total_disputed=5, dispute_rate_pct=9.1
        )),
    }
    for k, v in (repo_overrides or {}).items():
        defaults[k] = v
    for k, v in defaults.items():
        setattr(repo, k, v)

    config_svc.get_int = AsyncMock(return_value=48)
    for k, v in (config_overrides or {}).items():
        setattr(config_svc, k, v)

    return AnalyticsService.__new__(AnalyticsService), repo, config_svc


class TestGetMissionControl:
    async def test_returns_mission_control_dto(self):
        svc_raw, repo, config_svc = _make_svc()
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc

        result = await svc_raw.get_mission_control()

        assert isinstance(result, MissionControlDto)
        assert result.active_verifications == 5
        assert result.stuck_jobs == 1
        assert result.revenue_total_ngn == 100000.0

    async def test_reads_sla_hours_from_config(self):
        svc_raw, repo, config_svc = _make_svc()
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc
        config_svc.get_int = AsyncMock(return_value=72)

        await svc_raw.get_mission_control()

        repo.mission_control.assert_called_once_with(stuck_threshold_hours=72)

    async def test_zero_counts_when_no_data(self):
        svc_raw, repo, config_svc = _make_svc(repo_overrides={
            "mission_control": AsyncMock(return_value=MissionControlDto(
                active_verifications=0, pending_assignments=0, stuck_jobs=0,
                sla_at_risk_count=0, revenue_total_ngn=0.0, available_agents=0,
            ))
        })
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc

        result = await svc_raw.get_mission_control()
        assert result.active_verifications == 0
        assert result.revenue_total_ngn == 0.0


class TestGetAnalyticsDashboard:
    async def test_assembles_all_components(self):
        svc_raw, repo, config_svc = _make_svc()
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc

        result = await svc_raw.get_analytics_dashboard()

        assert isinstance(result, AnalyticsDashboardDto)
        assert result.conversion_funnel.signups == 100
        assert result.conversion_funnel.paid == 60
        assert result.dispute_rate.total_completed == 50

    async def test_conversion_percentages_correct(self):
        svc_raw, repo, config_svc = _make_svc(repo_overrides={
            "conversion_funnel": AsyncMock(return_value=ConversionFunnelDto(
                signups=200, submitted=150, paid=100, completed=80,
                signup_to_paid_pct=50.0, paid_to_completed_pct=80.0,
            ))
        })
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc

        result = await svc_raw.get_analytics_dashboard()
        assert result.conversion_funnel.signup_to_paid_pct == 50.0
        assert result.conversion_funnel.paid_to_completed_pct == 80.0

    async def test_dispute_rate_computation(self):
        svc_raw, repo, config_svc = _make_svc(repo_overrides={
            "dispute_rate": AsyncMock(return_value=DisputeRateDto(
                total_completed=90, total_disputed=10, dispute_rate_pct=10.0,
            ))
        })
        svc_raw._repo = repo
        svc_raw._config_svc = config_svc

        result = await svc_raw.get_analytics_dashboard()
        assert result.dispute_rate.dispute_rate_pct == 10.0
        assert result.dispute_rate.total_disputed == 10
