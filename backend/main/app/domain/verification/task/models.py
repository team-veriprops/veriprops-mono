"""Task domain models — PRD Phase 6-7 (S19, S21-S25).

A Task is one agent's work unit within a Verification. One Verification has
N tasks, one per tier-required role. Tasks have their own state machine:
PENDING → (ASSIGNED | ACCEPTED) → IN_PROGRESS → SUBMITTED → APPROVED.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, JSON, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class TaskRole(str, enum.Enum):
    FIELD = "FIELD"
    SURVEYOR = "SURVEYOR"
    REGISTRY = "REGISTRY"
    LAWYER = "LAWYER"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"      # admin directly assigned a specific agent
    ACCEPTED = "ACCEPTED"      # agent accepted (from pool or admin-assign)
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# Roles required per verification tier
TIER_ROLES: dict[str, List[TaskRole]] = {
    "BASIC": [TaskRole.REGISTRY],
    "STANDARD": [TaskRole.FIELD, TaskRole.SURVEYOR, TaskRole.REGISTRY],
    "PREMIUM": [TaskRole.FIELD, TaskRole.SURVEYOR, TaskRole.REGISTRY, TaskRole.LAWYER],
}


# ─── ORM ──────────────────────────────────────────────────────────


class Task(BaseEntity):
    __tablename__ = "tasks"

    verification_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False, index=True)
    agent_id = Column(String(36), nullable=True, index=True)
    status = Column(String(16), nullable=False, default=TaskStatus.PENDING.value, index=True)
    pool_released_at = Column(UTCDateTime, nullable=True)
    accepted_at = Column(UTCDateTime, nullable=True)
    submitted_at = Column(UTCDateTime, nullable=True)
    trust_score = Column(Integer, nullable=True)
    draft_payload = Column(Text, nullable=True)


class TaskAssignment(BaseEntity):
    __tablename__ = "task_assignments"

    task_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(36), nullable=False, index=True)
    assigned_by = Column(String(36), nullable=True)
    reassigned_from_id = Column(String(36), nullable=True)
    note = Column(Text, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────


class TaskDto(Object):
    id: str
    verification_id: str
    role: TaskRole
    agent_id: Optional[str] = None
    status: TaskStatus
    pool_released_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    trust_score: Optional[int] = None
    draft_payload: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class TaskAssignmentDto(Object):
    id: str
    task_id: str
    agent_id: str
    assigned_by: Optional[str] = None
    reassigned_from_id: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class CreateTaskDto(Object):
    verification_id: str
    role: TaskRole
    status: TaskStatus = TaskStatus.PENDING
    agent_id: Optional[str] = None
    pool_released_at: Optional[datetime] = None


class UpdateTaskDto(Object):
    status: Optional[TaskStatus] = None
    agent_id: Optional[str] = None
    pool_released_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    trust_score: Optional[int] = None
    draft_payload: Optional[str] = None


class QueryTaskDto(BaseQueryDto):
    verification_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class SearchTaskDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class CreateTaskAssignmentDto(Object):
    task_id: str
    agent_id: str
    assigned_by: Optional[str] = None
    reassigned_from_id: Optional[str] = None
    note: Optional[str] = None


class UpdateTaskAssignmentDto(Object):
    note: Optional[str] = None


class QueryTaskAssignmentDto(BaseQueryDto):
    task_id: Optional[str] = None
    agent_id: Optional[str] = None


class SearchTaskAssignmentDto(PageRequest, BaseQueryDto):
    task_id: Optional[str] = None
    agent_id: Optional[str] = None


# ── Request DTOs from API ──

class AdminAssignDto(Object):
    agent_id: str


class AdminReassignDto(Object):
    agent_id: str
    note: Optional[str] = None


class AvailableAgentDto(Object):
    agent_id: str
    user_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    types: List[str] = []
    coverage_states: List[str] = []
    active_task_count: int = 0
    rating: Optional[float] = None
    is_trusted: bool = False
    is_top_agent: bool = False
    composite_score: float = 0.0
