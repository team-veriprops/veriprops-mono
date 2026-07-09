"""Reputation & coverage DTOs (PRD §16). No entity — metrics are derived on read (D32);
coverage + availability live on the existing agent tables."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.coverage.models import AgentCoverageInputDto
from main.app.domain.user.agent.profile.models import AvailabilityStatus
from main.appodus_utils import Object


class AgentMetricsDto(Object):
    """Aggregated reputation metrics for an agent (§16.1)."""

    total_jobs: int
    completed_jobs: int
    completion_rate: int      # 0–100
    accuracy_score: float     # 0–5
    avg_quality: int          # 0–100
    timeliness_rate: int      # 0–100
    decline_count: int
    composite_score: int      # 0–100
    active_since: Optional[datetime] = None


class AgentProfileSummaryDto(Object):
    """The agent's own profile page (§16.1): metrics + coverage + availability."""

    metrics: AgentMetricsDto
    availability: AvailabilityStatus            # agent-set
    effective_availability: AvailabilityStatus  # forced RED at capacity
    active_task_count: int
    max_active_tasks: int
    approved_roles: List[AgentRole]
    active_roles: List[AgentRole]
    coverage: List[AgentCoverageInputDto]
    coverage_flagged_for_review: bool           # unusually wide coverage (§16.1)


class SetAvailabilityDto(Object):
    availability: AvailabilityStatus


class SuggestedAgentDto(Object):
    """One ranked candidate for a task assignment (§16.1, admin-only)."""

    user_id: str
    name: str
    composite_score: int
    accuracy_score: float
    completion_rate: int
    timeliness_rate: int
    availability: AvailabilityStatus            # effective
    active_task_count: int
    covers_area: bool                           # coverage matches the property location
    top_agent: bool                             # accuracy ≥ top-agent threshold
    low_performance: bool                       # composite < low-performance threshold
