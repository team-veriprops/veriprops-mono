"""Analytics domain DTOs — S53 Phase 18.

No ORM models here; aggregation reads existing tables.
"""
from __future__ import annotations

from typing import List, Optional

from main.appodus_utils import Object


class MissionControlDto(Object):
    active_verifications: int
    pending_assignments: int
    stuck_jobs: int
    sla_at_risk_count: int
    revenue_total_ngn: float
    available_agents: int


class RegionalStat(Object):
    region: str
    active_count: int
    completed_count: int
    avg_trust_score: Optional[float] = None
    revenue_ngn: float


class RegionalPerformanceDto(Object):
    regions: List[RegionalStat]


class ConversionFunnelDto(Object):
    signups: int
    submitted: int
    paid: int
    completed: int
    signup_to_paid_pct: float
    paid_to_completed_pct: float


class AvgVerificationTimeByTierDto(Object):
    tier: str
    avg_hours: float


class AgentPerformanceTrendDto(Object):
    period: str
    avg_quality_score: float
    total_scores: int


class RevenueByLocationDto(Object):
    state: str
    tier: str
    revenue_ngn: float
    count: int


class DisputeRateDto(Object):
    total_completed: int
    total_disputed: int
    dispute_rate_pct: float


class AnalyticsDashboardDto(Object):
    conversion_funnel: ConversionFunnelDto
    avg_time_by_tier: List[AvgVerificationTimeByTierDto]
    agent_performance_trends: List[AgentPerformanceTrendDto]
    revenue_by_location: List[RevenueByLocationDto]
    dispute_rate: DisputeRateDto
