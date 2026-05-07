"""KYC record domain — tracks each BVN verification and selfie-match event.

Separate from AgentApplication so that async webhook state (PENDING → resolved)
and admin review decisions are traceable per-event, not overwritten in-place.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class KycType(str, enum.Enum):
    BVN_VERIFICATION = "BVN_VERIFICATION"
    SELFIE_MATCH = "SELFIE_MATCH"


class KycStatus(str, enum.Enum):
    PENDING = "PENDING"          # awaiting async webhook result (selfie only)
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNDER_REVIEW = "UNDER_REVIEW"  # score < KYC_SELFIE_REVIEW_THRESHOLD → admin queue


class AdminKycDecision(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ─── ORM ──────────────────────────────────────────────────────────


class KycRecord(BaseEntity):
    __tablename__ = "kyc_records"

    application_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    kyc_type = Column(String(32), nullable=False)       # KycType
    status = Column(String(16), nullable=False, index=True)  # KycStatus
    provider = Column(String(32), nullable=False)       # "dojah" | "stub"
    provider_ref = Column(String(128), nullable=True, index=True)  # Dojah job/verification ID
    score = Column(Integer, nullable=True)              # 0–100; selfie match confidence
    failure_reason = Column(Text, nullable=True)
    webhook_payload = Column(JSON, nullable=True)       # raw webhook body for audit trail
    reviewed_by_admin_id = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    admin_decision = Column(String(8), nullable=True)   # AdminKycDecision
    admin_notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_kyc_records_app_type", "application_id", "kyc_type"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────


class CreateKycRecordDto(Object):
    application_id: str
    user_id: str
    kyc_type: KycType
    status: KycStatus
    provider: str
    provider_ref: Optional[str] = None
    score: Optional[int] = None
    failure_reason: Optional[str] = None


class UpdateKycRecordDto(Object):
    status: Optional[KycStatus] = None
    score: Optional[int] = None
    failure_reason: Optional[str] = None
    webhook_payload: Optional[Dict[str, Any]] = None
    reviewed_by_admin_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    admin_decision: Optional[AdminKycDecision] = None
    admin_notes: Optional[str] = None


class SearchKycRecordDto(PageRequest, BaseQueryDto):
    application_id: Optional[str] = None
    user_id: Optional[str] = None
    kyc_type: Optional[str] = None
    status: Optional[str] = None


class QueryKycRecordDto(BaseQueryDto):
    application_id: Optional[str] = None
    user_id: Optional[str] = None
    kyc_type: Optional[str] = None
    status: Optional[str] = None
    provider_ref: Optional[str] = None


class KycRecordDto(Object):
    id: str
    application_id: str
    user_id: str
    kyc_type: KycType
    status: KycStatus
    provider: str
    provider_ref: Optional[str] = None
    score: Optional[int] = None
    failure_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    admin_decision: Optional[AdminKycDecision] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminKycReviewDto(Object):
    decision: AdminKycDecision
    notes: Optional[str] = None
