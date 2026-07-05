"""Dispute domain (PRD §14.3)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Column, Index, String, Text

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import JSONB_VARIANT, UTCDateTime


class DisputeStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class DisputeOutcome(str, enum.Enum):
    """The three §14.3 resolutions."""

    REJECTED = "REJECTED"                # dispute not upheld → back to COMPLETED
    FULL_REFUND = "FULL_REFUND"          # upheld → REFUNDED
    PARTIAL_RECHECK = "PARTIAL_RECHECK"  # upheld partial → free re-check (→ IN_PROGRESS)


class DisputeType(str, enum.Enum):
    """Customer-declared category of the complaint (§14.3)."""

    INACCURATE_FINDING = "INACCURATE_FINDING"
    MISSING_CHECK = "MISSING_CHECK"
    AGENT_CONDUCT = "AGENT_CONDUCT"
    OTHER = "OTHER"


# ─── ORM ──────────────────────────────────────────────────────────

class Dispute(BaseEntity):
    __tablename__ = "disputes"

    verification_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    dispute_type = Column(String(24), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(JSONB_VARIANT, nullable=True)
    status = Column(String(16), nullable=False, default=DisputeStatus.OPEN.value, index=True)

    # Agent dispute-defence (admin-mediated) — the affected role's agent, their bounded-window
    # response, and when it was given. The agent never learns the customer's identity.
    target_role = Column(String(16), nullable=True)
    agent_id = Column(String(36), nullable=True, index=True)
    agent_defence_text = Column(Text, nullable=True)
    agent_defence_at = Column(UTCDateTime, nullable=True)

    # Admin resolution — the mandatory note is delivered verbatim to the customer (§14.3).
    resolution_outcome = Column(String(24), nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_disputes_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateDisputeDto(Object):
    verification_id: str
    customer_id: str
    dispute_type: DisputeType
    description: str
    evidence: Optional[List[dict]] = None
    target_role: Optional[AgentRole] = None
    agent_id: Optional[str] = None
    status: DisputeStatus = DisputeStatus.OPEN


class UpdateDisputeDto(Object):
    status: Optional[str] = None
    agent_defence_text: Optional[str] = None
    resolution_outcome: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None


class QueryDisputeDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchDisputeDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class OpenDisputeDto(Object):
    dispute_type: DisputeType
    description: str
    evidence: Optional[List[dict]] = None
    target_role: Optional[AgentRole] = None


class AgentDefenceDto(Object):
    text: str


class ResolveDisputeDto(Object):
    outcome: DisputeOutcome
    note: str
    scope_roles: Optional[List[AgentRole]] = None  # required for PARTIAL_RECHECK


class DisputeDto(Object):
    id: str
    verification_id: str
    dispute_type: DisputeType
    description: str
    evidence: Optional[List[Any]] = None
    status: DisputeStatus
    target_role: Optional[AgentRole] = None
    agent_defence_text: Optional[str] = None
    agent_defence_at: Optional[datetime] = None
    resolution_outcome: Optional[DisputeOutcome] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    date_created: datetime


def dispute_to_dto(d: "Dispute") -> DisputeDto:
    """Map a Dispute ORM row to its API DTO (shared by the service page + controller)."""
    return DisputeDto(
        id=d.id, verification_id=d.verification_id, dispute_type=DisputeType(d.dispute_type),
        description=d.description, evidence=d.evidence, status=DisputeStatus(d.status),
        target_role=AgentRole(d.target_role) if d.target_role else None,
        agent_defence_text=d.agent_defence_text, agent_defence_at=d.agent_defence_at,
        resolution_outcome=DisputeOutcome(d.resolution_outcome) if d.resolution_outcome else None,
        resolution_note=d.resolution_note, resolved_at=d.resolved_at, date_created=d.date_created,
    )
