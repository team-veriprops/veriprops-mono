"""Broadcast domain (PRD §18.1, D37) — an admin announcement to an audience.

A broadcast targets an audience (All / Admins / Customers / Agents), can be sent
immediately or scheduled, and fans out one in-app notification (+ email) per recipient
through the §4.8 event bus. Scheduled sends are fired by a swept job.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class BroadcastAudience(str, enum.Enum):
    ALL = "ALL"
    ADMINS = "ADMINS"
    CUSTOMERS = "CUSTOMERS"
    AGENTS = "AGENTS"


class BroadcastStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


# ─── ORM ──────────────────────────────────────────────────────────

class Broadcast(BaseEntity):
    __tablename__ = "broadcasts"

    audience = Column(String(16), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default=BroadcastStatus.DRAFT.value, index=True)
    scheduled_at = Column(UTCDateTime, nullable=True)
    sent_at = Column(UTCDateTime, nullable=True)
    recipient_count = Column(Integer, nullable=False, server_default="0")
    # created_by (the composing admin) is inherited from BaseEntity — set via the create DTO.

    __table_args__ = (
        Index("ix_broadcasts_status", "status"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateBroadcastDto(Object):
    audience: str
    subject: str
    body: str
    status: BroadcastStatus = BroadcastStatus.DRAFT
    scheduled_at: Optional[datetime] = None
    created_by: str


class UpdateBroadcastDto(Object):
    status: Optional[str] = None
    recipient_count: Optional[int] = None


class QueryBroadcastDto(BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


class SearchBroadcastDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class ComposeBroadcastDto(Object):
    """Create a broadcast (§18.1). ``scheduled_at`` present → SCHEDULED; absent → DRAFT."""

    audience: BroadcastAudience
    subject: str
    body: str
    scheduled_at: Optional[datetime] = None


class BroadcastPreviewDto(Object):
    audience: BroadcastAudience
    recipient_count: int


class BroadcastDto(Object):
    id: str
    audience: BroadcastAudience
    subject: str
    body: str
    status: BroadcastStatus
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    recipient_count: int = 0
    date_created: datetime
