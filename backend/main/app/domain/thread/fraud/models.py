"""Fraud flag models — PRD Phase 11 (S38)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class FraudReviewDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FraudFlag(BaseEntity):
    __tablename__ = "fraud_flags"

    message_id = Column(String(36), nullable=False, index=True)
    message_body = Column(Text, nullable=False)
    matched_patterns = Column(Text, nullable=False)  # JSON array of pattern names
    reviewed = Column(Boolean, nullable=False, default=False)
    review_decision = Column(String(16), nullable=True)
    reviewer_id = Column(String(36), nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class FraudFlagDto(Object):
    id: str
    message_id: str
    message_body: str
    matched_patterns: list
    reviewed: bool
    review_decision: Optional[FraudReviewDecision] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class CreateFraudFlagDto(Object):
    message_id: str
    message_body: str
    matched_patterns: str  # JSON


class UpdateFraudFlagDto(Object):
    reviewed: Optional[bool] = None
    review_decision: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class QueryFraudFlagDto(BaseQueryDto):
    reviewed: Optional[bool] = None


class SearchFraudFlagDto(PageRequest, BaseQueryDto):
    reviewed: Optional[bool] = None


class ReviewFraudFlagDto(Object):
    decision: FraudReviewDecision
