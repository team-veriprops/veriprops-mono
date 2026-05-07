"""Verification aggregate — PRD §0.2 / §1.3 / §5."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional


class PropertyDocumentType(str, enum.Enum):
    SURVEY_PLAN = "SURVEY_PLAN"
    TITLE_DOCUMENT = "TITLE_DOCUMENT"
    PURCHASE_AGREEMENT = "PURCHASE_AGREEMENT"
    OTHER = "OTHER"

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from main.app.domain.verification.property.models import PropertyDto, PropertyType, PropertySource
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class VerificationTier(str, enum.Enum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class VerificationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    IN_PROGRESS = "IN_PROGRESS"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


# ─── ORM ──────────────────────────────────────────────────────────


class Verification(BaseEntity):
    __tablename__ = "verifications"

    vid = Column(String(24), nullable=False, unique=True, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    property_id = Column(String(36), nullable=True)
    tier = Column(String(16), nullable=False, default=VerificationTier.BASIC.value)
    status = Column(String(24), nullable=False, default=VerificationStatus.DRAFT.value, index=True)
    pricing_snapshot = Column(Text, nullable=True)  # JSON
    consent_snapshot_id = Column(String(36), nullable=True)
    payment_id = Column(String(36), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Server-side wizard draft.
    draft_payload = Column(Text, nullable=True)  # JSON-encoded
    draft_step = Column(Integer, nullable=False, default=0)


# ─── DTOs ─────────────────────────────────────────────────────────


class CreateVerificationDto(Object):
    vid: str
    customer_id: str
    tier: VerificationTier = VerificationTier.BASIC
    status: VerificationStatus = VerificationStatus.DRAFT
    draft_step: int = 0


class UpdateVerificationDto(Object):
    tier: Optional[VerificationTier] = None
    status: Optional[VerificationStatus] = None
    property_id: Optional[str] = None
    pricing_snapshot: Optional[str] = None
    consent_snapshot_id: Optional[str] = None
    payment_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    draft_payload: Optional[str] = None
    draft_step: Optional[int] = None


class SearchVerificationDto(PageRequest, BaseQueryDto):
    customer_id: Optional[str] = None
    status: Optional[str] = None
    tier: Optional[str] = None


class QueryVerificationDto(BaseQueryDto):
    customer_id: Optional[str] = None
    status: Optional[str] = None
    tier: Optional[str] = None
    vid: Optional[str] = None


# ── Wizard step inputs ──


class WizardStepDto(Object):
    step: int
    payload: Dict[str, Any]


class TierSelectionDto(Object):
    tier: VerificationTier
    currency: str = "NGN"


class ConsentRecordDto(Object):
    document_type: str
    consent_version: str


class ConsentsAcceptedDto(Object):
    consents: List[ConsentRecordDto]


# ── Public read DTOs ──


class PricingLineItemDto(Object):
    label: str
    amount_minor: int
    description: Optional[str] = None


class PricingSnapshotDto(Object):
    tier: VerificationTier
    currency: str
    base_amount_minor: int
    line_items: List[PricingLineItemDto]
    total_amount_minor: int
    fx_rate: Optional[float] = None
    fx_source_currency: str = "NGN"
    fx_fetched_at: Optional[datetime] = None
    fx_stale: bool = False
    locked_at: Optional[datetime] = None
    locked_until: Optional[datetime] = None


class VerificationDto(Object):
    id: str
    vid: str
    customer_id: str
    tier: VerificationTier
    status: VerificationStatus
    property: Optional[PropertyDto] = None
    pricing: Optional[PricingSnapshotDto] = None
    submitted_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    draft_step: int = 0
    draft_payload: Optional[Dict[str, Any]] = None


class DocumentUploadResponseDto(Object):
    url: str
    document_type: PropertyDocumentType
