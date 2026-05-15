"""Broadcast domain models — S55 Phase 18."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class BroadcastStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class BroadcastAudience(str, enum.Enum):
    ALL = "ALL"
    CUSTOMERS = "CUSTOMERS"
    AGENTS = "AGENTS"
    ADMINS = "ADMINS"


class Broadcast(BaseEntity):
    __tablename__ = "broadcasts"

    subject = Column(String(256), nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)
    audience = Column(String(16), nullable=False, default=BroadcastAudience.ALL.value)
    channels = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default=BroadcastStatus.DRAFT.value, index=True)
    scheduled_at = Column(UTCDateTime, nullable=True)
    sent_at = Column(UTCDateTime, nullable=True)
    created_by = Column(String(36), nullable=True)
    total_recipients = Column(Integer, nullable=True)
    sent_count = Column(Integer, nullable=True, default=0)


# ─── DTOs ─────────────────────────────────────────────────────────


class BroadcastDto(Object):
    id: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    audience: BroadcastAudience
    channels: Optional[str] = None
    status: BroadcastStatus
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_by: Optional[str] = None
    total_recipients: Optional[int] = None
    sent_count: Optional[int] = None
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateBroadcastDto(Object):
    subject: str
    body_text: str
    body_html: Optional[str] = None
    audience: BroadcastAudience = BroadcastAudience.ALL
    channels: Optional[str] = None
    created_by: Optional[str] = None


class UpdateBroadcastDto(Object):
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    audience: Optional[BroadcastAudience] = None
    channels: Optional[str] = None
    status: Optional[BroadcastStatus] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    total_recipients: Optional[int] = None
    sent_count: Optional[int] = None


class QueryBroadcastDto(BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


class SearchBroadcastDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


class ScheduleBroadcastDto(Object):
    scheduled_at: datetime


class PreviewBroadcastDto(Object):
    subject: str
    body_text: str
    body_html: Optional[str] = None
    audience: BroadcastAudience
    estimated_recipients: int
