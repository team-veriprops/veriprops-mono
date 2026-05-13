"""Conflict detection models — PRD Phase 8 (S29)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ConflictSeverity(str, enum.Enum):
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


class ConflictStatus(str, enum.Enum):
    OPEN = "OPEN"
    OVERRIDDEN = "OVERRIDDEN"
    TASK_REJECTED = "TASK_REJECTED"


class ConflictFlag(BaseEntity):
    __tablename__ = "conflict_flags"

    verification_id = Column(String(36), nullable=False, index=True)
    rule_id = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False, default=ConflictSeverity.BLOCKER.value)
    description = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default=ConflictStatus.OPEN.value, index=True)
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_conflict_flags_vid_status", "verification_id", "status"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class ConflictFlagDto(Object):
    id: str
    verification_id: str
    rule_id: str
    severity: ConflictSeverity
    description: str
    status: ConflictStatus
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateConflictFlagDto(Object):
    verification_id: str
    rule_id: str
    severity: ConflictSeverity
    description: str
    status: ConflictStatus = ConflictStatus.OPEN


class UpdateConflictFlagDto(Object):
    status: Optional[ConflictStatus] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class QueryConflictFlagDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchConflictFlagDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class ResolveConflictDto(Object):
    action: str  # "OVERRIDE" or "REJECT_TASK"
    note: str
    task_id_to_reject: Optional[str] = None
