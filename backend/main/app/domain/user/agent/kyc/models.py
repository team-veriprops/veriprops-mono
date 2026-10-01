"""Agent KYC-record domain (PRD §3.1).

Persists the KYC provider's decision and reference. When the application reaches a reviewer,
the selfie — and for a passport, driver's licence or voter's card, a photo of the document —
is kept in private, encrypted storage so the reviewer can compare them; the record holds only
their storage keys, and a reviewer reads them through short-lived links. Erasure deletes them.
BVN is primary; government-ID is the fallback (see ``KycSubmissionDto``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import SecretStr
from sqlalchemy import Column, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
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
    # The government ID type, for the GOV_ID method; the reviewer's comparison is labelled by it.
    id_type = Column(String(24), nullable=True)
    # Private storage keys of the images a reviewer compares; None when nothing was kept.
    selfie_key = Column(String(255), nullable=True)
    document_key = Column(String(255), nullable=True)


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
    id_type: Optional[str] = None
    selfie_key: Optional[str] = None
    document_key: Optional[str] = None


class UpdateKycRecordDto(Object):
    status: Optional[str] = None
    score: Optional[int] = None
    summary: Optional[str] = None


class SearchKycRecordDto(InternalPageRequest, BaseQueryDto):
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
    """KYC input at submission (PRD §3.1 step 2). BVN primary; gov-ID fallback.

    The images are base64 JPEG/PNG (a ``data:`` prefix is accepted) and `SecretStr`, so a log
    line that prints the submission prints no face."""

    method: KycMethod
    bvn: Optional[str] = None
    id_type: Optional[GovIdType] = None
    id_number: Optional[str] = None
    selfie_image: SecretStr
    # A photo of the ID, for the types a person checks (passport, driver's licence, voter's card).
    id_document_image: Optional[SecretStr] = None


class KycRecordDto(Object):
    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    id_type: Optional[GovIdType] = None
    score: Optional[int] = None
    summary: Optional[str] = None
    verified_at: Optional[datetime] = None
    # Short-lived links a reviewer reads the stored images through (admin view only).
    selfie_url: Optional[str] = None
    document_url: Optional[str] = None


class KycReviewImagesDto(Object):
    selfie_url: Optional[str] = None
    document_url: Optional[str] = None
