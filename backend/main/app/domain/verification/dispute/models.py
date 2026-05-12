"""Dispute domain — S46."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class DisputeStatus(str, enum.Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


class DisputeOutcome(str, enum.Enum):
    REJECTED = "REJECTED"
    FULL_REFUND = "FULL_REFUND"
    PARTIAL_RECHECK = "PARTIAL_RECHECK"


class Dispute(BaseEntity):
    __tablename__ = "disputes"

    verification_id = Column(String(36), nullable=False, index=True)
    dispute_type = Column(String(40), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default=DisputeStatus.PENDING.value)
    submitted_by = Column(String(36), nullable=False)
    submitted_at = Column(UTCDateTime, nullable=False)


class DisputeResolution(BaseEntity):
    __tablename__ = "dispute_resolutions"

    dispute_id = Column(String(36), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(String(36), nullable=False)
    resolved_at = Column(UTCDateTime, nullable=False)


class DisputeDto(Object):
    id: str
    verification_id: str
    dispute_type: str
    description: str
    status: DisputeStatus
    submitted_by: str
    submitted_at: str
    date_created: str


class DisputeResolutionDto(Object):
    id: str
    dispute_id: str
    outcome: DisputeOutcome
    resolution_note: Optional[str] = None
    resolved_by: str
    resolved_at: str


class SubmitDisputeDto(Object):
    dispute_type: str
    description: str


class ResolveDisputeDto(Object):
    outcome: DisputeOutcome
    resolution_note: Optional[str] = None


class CreateDisputeDto(Object):
    verification_id: str
    dispute_type: str
    description: str
    status: str = DisputeStatus.PENDING.value
    submitted_by: str
    submitted_at: str


class UpdateDisputeDto(Object):
    status: Optional[str] = None


class CreateDisputeResolutionDto(Object):
    dispute_id: str
    outcome: str
    resolution_note: Optional[str] = None
    resolved_by: str
    resolved_at: str


class QueryDisputeDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchDisputeDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None
    verification_id: Optional[str] = None
