"""Analytics DTOs (PRD §18.1) — orchestration-only, no ORM entity.

Every figure is derived server-side from the operational tables (backend is the source
of truth); the admin dashboard renders them, never computes them.
"""
from __future__ import annotations

from typing import List, Optional

from main.app.core.state.status import VerificationTier
from main.appodus_utils import Object


class FunnelDto(Object):
    """Conversion funnel (§18.1): how many verifications reach each lifecycle stage."""

    created: int = 0
    submitted: int = 0
    paid: int = 0
    completed: int = 0
    submit_rate: float = 0.0     # submitted / created
    payment_rate: float = 0.0    # paid / submitted
    completion_rate: float = 0.0  # completed / paid


class TierTimeDto(Object):
    tier: VerificationTier
    avg_days: float = 0.0
    completed_count: int = 0


class TierRevenueDto(Object):
    tier: VerificationTier
    revenue_minor: int = 0
    count: int = 0


class LocationRevenueDto(Object):
    state: str
    revenue_minor: int = 0
    count: int = 0


class RevenueDto(Object):
    total_minor: int = 0
    by_tier: List[TierRevenueDto] = []
    by_location: List[LocationRevenueDto] = []


class RegionalRowDto(Object):
    state: str
    active: int = 0
    completed: int = 0
    avg_trust_score: Optional[float] = None
    revenue_minor: int = 0


class AgentTrendPointDto(Object):
    month: str            # "YYYY-MM"
    completed_tasks: int = 0
    avg_quality: Optional[float] = None


class AgentTrendsDto(Object):
    points: List[AgentTrendPointDto] = []
