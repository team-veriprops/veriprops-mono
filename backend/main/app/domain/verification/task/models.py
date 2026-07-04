"""Verification task domain (PRD §2.2, §4.2, §6, §7).

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

from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, String, UniqueConstraint

from main.app.core.state.status import AgentRole, TaskState, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class TaskAssignmentMode(str, enum.Enum):
    """How the agent came to own the task (PRD §2.2)."""

    MANUAL = "MANUAL"        # admin picked the agent
    BROADCAST = "BROADCAST"  # open pool, first-accept-wins


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
    # Broadcast starvation timeout — past this the sweep escalates to targeted (§7.2).
    pool_expires_at = Column(UTCDateTime, nullable=True)
    # Manual-assign accept deadline — past this the no-show sweep returns to pool (§7.2).
    accept_deadline_at = Column(UTCDateTime, nullable=True)
    decline_count = Column(Integer, nullable=False, server_default="0")
    # Optional flat remote-job bonus attached to an aging/hard-to-reach task (§7.2).
    remote_bonus_minor = Column(BigInteger, nullable=True)

    assigned_at = Column(UTCDateTime, nullable=True)
    accepted_at = Column(UTCDateTime, nullable=True)
    submitted_at = Column(UTCDateTime, nullable=True)
    approved_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        # A verification has at most one task per role; reassignment/rework reuse the row.
        UniqueConstraint("verification_id", "role", name="uq_verification_tasks_role"),
        Index("ix_verification_tasks_state", "state"),
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


class SearchTaskDto(PageRequest, BaseQueryDto):
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
