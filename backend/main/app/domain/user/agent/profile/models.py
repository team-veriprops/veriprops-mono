"""Agent application profile domain (PRD §3.1–3.2).

The core onboarding entity: a User applying for one or more AGENT roles, its
review lifecycle (PENDING → APPROVED/REJECTED) and the roles an admin cleared.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.mutable import MutableList

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime, jsonb_variant


class AgentApplicationStatus(str, enum.Enum):
    """Lifecycle of an agent application (PRD §3.1: PENDING → APPROVED/REJECTED)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AvailabilityStatus(str, enum.Enum):
    """Agent availability signal (PRD §16.1). 🟢 accepting work, 🟡 limited, 🔴 unavailable.
    The *effective* availability is forced to RED at ``agent_max_active_tasks`` regardless of
    the agent's set value."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


# ─── ORM ──────────────────────────────────────────────────────────

class AgentProfile(BaseEntity):
    __tablename__ = "agent_profiles"

    user_id = Column(String(36), nullable=False, index=True)
    # Roles the applicant is being reviewed for (PRD §3.1 step 1, multi-select).
    roles = Column(MutableList.as_mutable(jsonb_variant()), nullable=False, default=list)
    # Roles cleared by admin — the subset of ``roles`` the agent may work.
    approved_roles = Column(MutableList.as_mutable(jsonb_variant()), nullable=False, default=list)
    status = Column(String(16), nullable=False, default=AgentApplicationStatus.PENDING.value, index=True)
    rejection_reason = Column(String(500), nullable=True)
    bio = Column(String(300), nullable=True)
    years_experience = Column(Integer, nullable=True)
    # Agent-set availability signal (§16.1); effective value is forced RED at capacity.
    availability = Column(String(8), nullable=False, default=AvailabilityStatus.GREEN.value)
    submitted_at = Column(UTCDateTime, nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    # status index is declared inline (index=True) → ix_agent_profiles_status, matching the migration.


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAgentProfileDto(Object):
    user_id: str
    roles: List[AgentRole]
    status: AgentApplicationStatus = AgentApplicationStatus.PENDING
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    submitted_at: Optional[datetime] = None


class UpdateAgentProfileDto(Object):
    roles: Optional[List[str]] = None
    approved_roles: Optional[List[str]] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    availability: Optional[str] = None
    reviewed_by: Optional[str] = None


class SearchAgentProfileDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class QueryAgentProfileDto(BaseQueryDto):
    user_id: Optional[str] = None
    roles: Optional[List[str]] = None
    approved_roles: Optional[List[str]] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
