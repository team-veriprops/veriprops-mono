"""Consent (consent_versioned) — PRD §3.2 / S57 (R19.4)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class ConsentDocumentType(str, enum.Enum):
    PLATFORM_TERMS = "PLATFORM_TERMS"
    PRIVACY_POLICY = "PRIVACY_POLICY"
    AGENT_TERMS = "AGENT_TERMS"
    VERIFICATION_TERMS = "VERIFICATION_TERMS"
    REPORT_DISCLAIMER = "REPORT_DISCLAIMER"
    # Phase 5 — verification submission consents (PRD §5.3)
    VERIFICATION_DISCLAIMER = "VERIFICATION_DISCLAIMER"
    FINDINGS_OPINION_ACK = "FINDINGS_OPINION_ACK"
    JURISDICTION_PLATFORM_ONLY = "JURISDICTION_PLATFORM_ONLY"
    COMMUNICATION_RECORDING = "COMMUNICATION_RECORDING"
    REFUND_POLICY = "REFUND_POLICY"


class ConsentSignoffStatus(str, enum.Enum):
    """Whether a legal document's prose is finalised by counsel.

    DRAFT prose is built and shown (with a visible banner) but its exact wording
    is on the §B legal sign-off list — go-live, not build, is gated. FINAL prose
    is cleared for production.
    """
    DRAFT = "DRAFT"
    FINAL = "FINAL"


class ConsentDocument(BaseEntity):
    __tablename__ = "consent_documents"

    type = Column(String(32), nullable=False, index=True)
    # Document version — distinct from BaseEntity.version (optimistic locking).
    consent_version = Column(String(16), nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    title = Column(String(255), nullable=False)
    href = Column(String(255), nullable=False)
    # Markdown prose of the legal document; populated by the runtime seeder from
    # the code content registry (kept out of the migration so prose stays editable).
    body = Column(Text, nullable=True)
    signoff_status = Column(String(16), nullable=False, server_default=ConsentSignoffStatus.DRAFT.value)

    __table_args__ = (
        UniqueConstraint("type", "consent_version", name="uq_consent_type_consent_version"),
        Index("ix_consent_active_lookup", "type", "effective_at"),
    )


class UserConsent(BaseEntity):
    __tablename__ = "user_consents"

    user_id = Column(String(36), nullable=False, index=True)
    document_type = Column(String(32), nullable=False)
    consent_version = Column(String(16), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(64), nullable=True)
    device_fingerprint = Column(String(128), nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────
class UserConsentInputDto(Object):
    document_type: ConsentDocumentType
    consent_version: str
    accepted_at: datetime


class CreateConsentDocumentDto(Object):
    type: ConsentDocumentType
    consent_version: str
    effective_at: datetime
    title: str
    href: str
    body: Optional[str] = None
    signoff_status: ConsentSignoffStatus = ConsentSignoffStatus.DRAFT


class UpdateConsentDocumentDto(Object):
    # effective_at is intentionally not updatable here: a new effective date means
    # a new (type, consent_version) row (create path). The update path only refreshes
    # editorial fields, avoiding the repo's jsonable_encoder datetime→str coercion.
    title: Optional[str] = None
    href: Optional[str] = None
    body: Optional[str] = None
    signoff_status: Optional[ConsentSignoffStatus] = None


class SearchConsentDocumentDto(PageRequest, BaseQueryDto):
    type: Optional[str] = None
    consent_version: Optional[str] = None


class QueryConsentDocumentDto(BaseQueryDto):
    type: Optional[str] = None
    consent_version: Optional[str] = None
    effective_at: Optional[datetime] = None
    title: Optional[str] = None
    href: Optional[str] = None


class CreateUserConsentDto(Object):
    user_id: str
    document_type: ConsentDocumentType
    consent_version: str
    accepted_at: datetime
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None


class UpdateUserConsentDto(Object):
    pass


class SearchUserConsentDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    document_type: Optional[str] = None
    consent_version: Optional[str] = None


class QueryUserConsentDto(BaseQueryDto):
    user_id: Optional[str] = None
    document_type: Optional[str] = None
    consent_version: Optional[str] = None
    accepted_at: Optional[datetime] = None


class ConsentDocumentDto(Object):
    type: ConsentDocumentType
    consent_version: str
    effective_at: datetime
    title: str
    href: str


class MissingConsentsDto(Object):
    documents: List[ConsentDocumentDto]


# ─── Public legal-document read DTOs (rendered on the marketing /legal/* pages) ──

class LegalDocumentSummaryDto(Object):
    """Metadata for a published legal document (no body) — for sitemaps / listings."""
    type: ConsentDocumentType
    consent_version: str
    effective_at: datetime
    title: str
    href: str
    signoff_status: ConsentSignoffStatus


class LegalDocumentDto(LegalDocumentSummaryDto):
    """Full published legal document including its Markdown body."""
    body: Optional[str] = None


class LegalDocumentListDto(Object):
    documents: List[LegalDocumentSummaryDto]


class AcceptConsentsDto(Object):
    consents: List[UserConsentInputDto]


# ─── S57 — R19.4 consent history DTOs ───────────────────────────────


class UserConsentHistoryItemDto(Object):
    document_type: str
    consent_version: str
    accepted_at: datetime
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None


class UserConsentHistoryPageDto(Object):
    items: List[UserConsentHistoryItemDto]
    total: int
    page: int
    page_size: int
