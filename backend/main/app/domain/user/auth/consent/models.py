"""Consent (consent_versioned) — PRD §3.2."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint

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


class ConsentDocument(BaseEntity):
    __tablename__ = "consent_documents"

    type = Column(String(32), nullable=False, index=True)
    consent_version = Column(String(16), nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    title = Column(String(255), nullable=False)
    href = Column(String(255), nullable=False)

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


class UpdateConsentDocumentDto(Object):
    title: Optional[str] = None
    href: Optional[str] = None


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


class AcceptConsentsDto(Object):
    consents: List[UserConsentInputDto]
