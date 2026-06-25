"""Admin verification domain models — PRD Phase 6 (R6.1, R6.2, R6.5)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Boolean, String, Text

from main.app.domain.verification.models import VerificationStatus, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import JSONB_VARIANT


# ─── ORM ──────────────────────────────────────────────────────────


class VerificationNote(BaseEntity):
    __tablename__ = "verification_notes"

    verification_id = Column(String(36), nullable=False, index=True)
    admin_id = Column(String(36), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tags = Column(JSONB_VARIANT, nullable=True)
    pinned = Column(Boolean, nullable=False, default=False)


# ─── DTOs ─────────────────────────────────────────────────────────


class VerificationNoteDto(Object):
    id: str
    verification_id: str
    admin_id: str
    content: str
    tags: Optional[List[str]] = None
    pinned: bool = False
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateVerificationNoteDto(Object):
    verification_id: str
    admin_id: str
    content: str
    tags: Optional[List[str]] = None
    pinned: bool = False


class UpdateVerificationNoteDto(Object):
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    pinned: Optional[bool] = None


class QueryVerificationNoteDto(BaseQueryDto):
    verification_id: Optional[str] = None
    admin_id: Optional[str] = None
    pinned: Optional[bool] = None


class SearchVerificationNoteDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    pinned: Optional[bool] = None


# ── Admin request/response DTOs ──

class AddNoteDto(Object):
    content: str
    tags: Optional[List[str]] = None
    pinned: bool = False


class UpdateNoteDto(Object):
    pinned: Optional[bool] = None
    tags: Optional[List[str]] = None


class SetDelayDto(Object):
    delay_hours: int
    reason: str


class AdminFailDto(Object):
    reason: str


class AdminVerificationListItemDto(Object):
    id: str
    vid: str
    customer_id: str
    tier: VerificationTier
    status: VerificationStatus
    state: Optional[str] = None
    lga: Optional[str] = None
    address_line: Optional[str] = None
    submitted_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    date_created: datetime
    date_updated: Optional[datetime] = None


class AdminVerificationDetailDto(Object):
    id: str
    vid: str
    customer_id: str
    tier: VerificationTier
    status: VerificationStatus
    property: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None
    notes: List[VerificationNoteDto] = []
    submitted_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    date_created: datetime
    date_updated: Optional[datetime] = None


class AdminVerificationSearchDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None
    tier: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    vid: Optional[str] = None
