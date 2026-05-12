"""Re-check request domain — S44."""
from __future__ import annotations

import enum
from typing import List, Optional

from sqlalchemy import Boolean, Column, Numeric, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class RecheckStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RecheckRequest(BaseEntity):
    __tablename__ = "recheck_requests"

    verification_id = Column(String(36), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    scope_roles = Column(Text, nullable=False)  # JSON array
    status = Column(String(16), nullable=False, default=RecheckStatus.PENDING.value)
    requested_by = Column(String(36), nullable=False)
    reviewed_by = Column(String(36), nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)


class RecheckRequestDto(Object):
    id: str
    verification_id: str
    reason: str
    scope_roles: List[str]
    status: RecheckStatus
    requested_by: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    price: Optional[float] = None
    date_created: str


class SubmitRecheckDto(Object):
    reason: str
    scope_roles: List[str]


class ReviewRecheckDto(Object):
    rejection_reason: Optional[str] = None


class CreateRecheckRequestDto(Object):
    verification_id: str
    reason: str
    scope_roles: str  # JSON serialized
    status: str = RecheckStatus.PENDING.value
    requested_by: str
    price: Optional[float] = None


class UpdateRecheckRequestDto(Object):
    status: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class QueryRecheckRequestDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None
    requested_by: Optional[str] = None


class SearchRecheckRequestDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None
    verification_id: Optional[str] = None
