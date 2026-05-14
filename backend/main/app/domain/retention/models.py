"""Data retention & erasure models — PRD Phase 19 (S58)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ErasureStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class DataErasureRequest(BaseEntity):
    __tablename__ = "data_erasure_requests"

    user_id = Column(String(36), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default=ErasureStatus.PENDING.value)
    requested_at = Column(UTCDateTime, nullable=False)
    reviewed_by = Column(String(36), nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)
    executed_at = Column(UTCDateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class ErasureRequestDto(Object):
    id: str
    user_id: str
    reason: Optional[str] = None
    status: ErasureStatus
    requested_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class CreateErasureRequestDto(Object):
    user_id: str
    reason: Optional[str] = None
    status: str = ErasureStatus.PENDING.value
    requested_at: datetime


class UpdateErasureRequestDto(Object):
    status: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class QueryErasureRequestDto(BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class SearchErasureRequestDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class ErasureRequestPageDto(Object):
    items: list[ErasureRequestDto]
    total: int
    page: int
    page_size: int
