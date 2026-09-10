"""Verification task domain (PRD §2.2, §4.2, §6, §12).

One per-role unit of work on a verification (Field / Surveyor / Registry / Lawyer).
Its lifecycle is the task state machine (``core/state/machine.py``); the global
verification status is *derived* from the set of task states by the derivation
owner (§4.1), never set on the task directly.

Two assignment paths (§2.2):
- **Manual** — admin assigns a specific agent: ``PENDING → ASSIGNED → ACCEPTED``.
- **Broadcast** — task enters the open pool at PAID (``auto_assignment_enabled``);
  first agent to accept wins: ``PENDING → ACCEPTED``.

Dependency-blocked roles (the Premium Lawyer, §4.2) are **not** instantiated as
rows until their upstream siblings reach ``SUBMITTED`` — so a not-yet-created
Lawyer task never drags the verification into ``UNDER_REVIEW`` early (§2.5).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from typing import Any, Dict

from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, String, UniqueConstraint

from main.app.core.state.status import AgentRole, TaskState, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT


class TaskAssignmentMode(str, enum.Enum):
    """How the agent came to own the task (PRD §2.2)."""

    MANUAL = "MANUAL"        # admin picked the agent
    BROADCAST = "BROADCAST"  # open pool, first-accept-wins


class ReviewDecision(str, enum.Enum):
    """Admin review outcome recorded on ``VerificationTask.review_decision`` (§8.3).
    Distinct from ``TaskState`` — the decision is the admin's verdict on a SUBMITTED task,
    while the state tracks the task's lifecycle position."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ─── ORM ──────────────────────────────────────────────────────────

class VerificationTask(BaseEntity):
    __tablename__ = "verification_tasks"

    verification_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    tier = Column(String(16), nullable=False)  # denormalised from the verification for filtering/commission
    state = Column(String(16), nullable=False, default=TaskState.PENDING.value, index=True)

    assigned_agent_id = Column(String(36), nullable=True, index=True)
    assignment_mode = Column(String(16), nullable=True)
    # In the open broadcast pool awaiting the first accept (§2.2, §6.2).
    in_pool = Column(Boolean, nullable=False, server_default="false")
    # Broadcast starvation timeout — past this the sweep escalates to targeted (§11.4).
    pool_expires_at = Column(UTCDateTime, nullable=True)
    # Manual-assign accept deadline — past this the no-show sweep returns to pool (§11.4).
    accept_deadline_at = Column(UTCDateTime, nullable=True)
    decline_count = Column(Integer, nullable=False, server_default="0")
    # Optional flat remote-job bonus attached to an aging/hard-to-reach task (§11.3).
    remote_bonus_minor = Column(BigInteger, nullable=True)

    assigned_at = Column(UTCDateTime, nullable=True)
    accepted_at = Column(UTCDateTime, nullable=True)
    submitted_at = Column(UTCDateTime, nullable=True)
    approved_at = Column(UTCDateTime, nullable=True)

    # Role-specific structured findings captured on submit (§12.2) — the shape differs
    # per role (Registry search, Field inspection, Surveyor measurement, Lawyer opinion).
    # Held as JSON so each role form evolves without a schema change; evidence binaries
    # live in the task_evidence child domain.
    submission_payload = Column(JSONB_VARIANT, nullable=True)
    rejection_reason = Column(String(1000), nullable=True)
    # Admin review outcome recorded during report review (§8.3). APPROVED here is the
    # admin's *intent*; the task only transitions SUBMITTED→APPROVED at explicit release,
    # so all-approved never auto-completes without the release gate. REJECTED sends the
    # task back to rework immediately.
    review_decision = Column(String(16), nullable=True)
    # Per-task quality (0–100) the admin sets on approval; blended into the composite
    # trust score by the tier weights (§8.3). Defaults to 100.
    review_quality = Column(Integer, nullable=False, server_default="100")
    # Optional one-line admin note surfaced to the customer as interim reassurance once
    # the task is review-approved (§9.3). Never shown before approval, so a risk-bearing
    # finding is only delivered with context after admin review.
    interim_note = Column(String(280), nullable=True)

    __table_args__ = (
        # A verification has at most one task per role; reassignment/rework reuse the row.
        UniqueConstraint("verification_id", "role", name="uq_verification_tasks_role"),
        # state index is declared inline (index=True) → ix_verification_tasks_state.
        Index("ix_verification_tasks_agent", "assigned_agent_id"),
    )


# ─── persistence DTOs ─────────────────────────────────────────────

class CreateTaskDto(Object):
    verification_id: str
    role: AgentRole
    tier: VerificationTier
    state: TaskState = TaskState.PENDING
    in_pool: bool = False


class UpdateTaskDto(Object):
    state: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    assignment_mode: Optional[str] = None
    in_pool: Optional[bool] = None
    decline_count: Optional[int] = None
    remote_bonus_minor: Optional[int] = None
    submission_payload: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    review_decision: Optional[str] = None
    review_quality: Optional[int] = None
    interim_note: Optional[str] = None


class SearchTaskDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    state: Optional[str] = None
    role: Optional[str] = None


class QueryTaskDto(BaseQueryDto):
    verification_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    state: Optional[str] = None
    role: Optional[str] = None
    tier: Optional[str] = None


# ─── API / read DTOs ──────────────────────────────────────────────

class TaskDto(Object):
    """Per-role task row shown in the admin verification detail grid."""

    id: str
    verification_id: str
    role: AgentRole
    tier: VerificationTier
    state: TaskState
    assigned_agent_id: Optional[str] = None
    assignment_mode: Optional[TaskAssignmentMode] = None
    in_pool: bool = False
    pool_expires_at: Optional[datetime] = None
    accept_deadline_at: Optional[datetime] = None
    decline_count: int = 0
    remote_bonus_minor: Optional[int] = None
    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class AssignTaskDto(Object):
    """Admin manual assignment / reassignment of a role to a specific agent."""

    agent_id: str


class DeclineTaskDto(Object):
    """Agent declines an assigned/accepted task (§12.1). Returns it to the pool."""

    reason: Optional[str] = None


class SubmitTaskDto(Object):
    """Agent submits role findings (§12.2). ``payload`` is the role-specific form;
    validated by the task validator per role. Evidence binaries are uploaded separately."""

    payload: Dict[str, Any]


class AgentTaskDto(Object):
    """A task as the owning/eligible agent sees it (agent dashboard, §12.1)."""

    id: str
    verification_id: str
    role: AgentRole
    tier: VerificationTier
    state: TaskState
    in_pool: bool = False
    assignment_mode: Optional[TaskAssignmentMode] = None
    accept_deadline_at: Optional[datetime] = None
    remote_bonus_minor: Optional[int] = None
    submission_payload: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    evidence_count: int = 0
    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None


class AgentDashboardDto(Object):
    """Agent home summary (§12) — backend-derived counts over the agent's own tasks so the
    dashboard renders workload at a glance."""

    assigned: int = 0      # ASSIGNED — awaiting the agent's accept
    active: int = 0        # ACCEPTED + IN_PROGRESS + REJECTED (rework) — work in hand
    submitted: int = 0     # SUBMITTED — awaiting admin review
    approved: int = 0      # APPROVED — released
    total: int = 0
    state_counts: Dict[TaskState, int] = {}
