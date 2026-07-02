"""Agent KYC-record domain (PRD §3.1).

Persists the KYC provider's *decision and reference only* — never raw biometrics.
BVN is primary; government-ID is the fallback (see ``KycSubmissionDto``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.integrations.kyc.models import (
    GovIdType,
    KycMethod,
    KycProvider,
    KycResultStatus,
)


# ─── ORM ──────────────────────────────────────────────────────────

class KycRecord(BaseEntity):
    """Persisted KYC provider outcome (PRD §3.1). Stores the provider's decision
    and reference only — never raw biometrics."""

    __tablename__ = "kyc_records"

    user_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    method = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    provider_ref = Column(String(255), nullable=False)
    score = Column(Integer, nullable=True)
    summary = Column(String(500), nullable=True)
    verified_at = Column(UTCDateTime, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateKycRecordDto(Object):
    user_id: str
    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    provider_ref: str
    score: Optional[int] = None
    summary: Optional[str] = None
    verified_at: Optional[datetime] = None


class UpdateKycRecordDto(Object):
    status: Optional[str] = None
    score: Optional[int] = None
    summary: Optional[str] = None


class SearchKycRecordDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class QueryKycRecordDto(BaseQueryDto):
    user_id: Optional[str] = None
    provider: Optional[str] = None
    method: Optional[str] = None
    status: Optional[str] = None
    provider_ref: Optional[str] = None
    score: Optional[int] = None


# ─── API request/response DTOs ────────────────────────────────────

class KycSubmissionDto(Object):
    """KYC input at submission (PRD §3.1 step 2). BVN primary; gov-ID fallback."""

    method: KycMethod
    bvn: Optional[str] = None
    id_type: Optional[GovIdType] = None
    id_number: Optional[str] = None
    # Access-controlled S3 reference for the uploaded selfie/ID (never the bytes).
    selfie_reference: Optional[str] = None
    document_ref: Optional[str] = None


class KycRecordDto(Object):
    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    score: Optional[int] = None
    summary: Optional[str] = None
    verified_at: Optional[datetime] = None
