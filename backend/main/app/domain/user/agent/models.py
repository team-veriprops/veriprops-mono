"""Agent application domain — PRD §3 / Phase 3 (Agent Onboarding & KYC).

A single AgentApplication row tracks an applicant from DRAFT through PENDING
(submitted), and into APPROVED or REJECTED. Wizard payloads land in this row
incrementally — no separate draft table — because the row is bound to user_id
and is mutable until submission.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.ext.mutable import MutableList, MutableDict

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class AgentType(str, enum.Enum):
    FIELD = "FIELD"
    SURVEYOR = "SURVEYOR"
    REGISTRY = "REGISTRY"
    LAWYER = "LAWYER"


class AgentApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class KycMethod(str, enum.Enum):
    BVN = "BVN"
    ID_DOC = "ID_DOC"


class IdDocType(str, enum.Enum):
    NIN = "NIN"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENCE = "DRIVERS_LICENCE"
    VOTERS_CARD = "VOTERS_CARD"


# ─── ORM ──────────────────────────────────────────────────────────

class AgentApplication(BaseEntity):
    __tablename__ = "agent_applications"

    user_id = Column(String(36), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default=AgentApplicationStatus.DRAFT.value, index=True)

    # Step 1 — Type selection (multi-select)
    types = Column(MutableList.as_mutable(JSON), nullable=False, default=list)

    # Step 2 — KYC
    kyc_method = Column(String(16), nullable=True)
    bvn_last4 = Column(String(4), nullable=True)
    bvn_verification_id = Column(String(128), nullable=True)
    bvn_verified_at = Column(DateTime(timezone=True), nullable=True)
    id_doc_type = Column(String(32), nullable=True)
    id_doc_url = Column(String(512), nullable=True)
    selfie_url = Column(String(512), nullable=True)
    selfie_match_score = Column(Integer, nullable=True)  # 0–100
    selfie_matched_at = Column(DateTime(timezone=True), nullable=True)

    # Step 3 — Professional credentials (conditional)
    surveyor_licence_no = Column(String(64), nullable=True)
    surveyor_licence_url = Column(String(512), nullable=True)
    nba_licence_no = Column(String(64), nullable=True)
    nba_licence_url = Column(String(512), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    coverage_states = Column(MutableList.as_mutable(JSON), nullable=False, default=list)
    coverage_lgas = Column(MutableList.as_mutable(JSON), nullable=False, default=list)
    bio = Column(Text, nullable=True)

    # Step 4 — Submission
    truthfulness_acknowledged = Column(String(8), nullable=True)
    agent_terms_consent_id = Column(String(36), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    # Admin review
    reviewed_by_admin_id = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agent_applications_status_submitted", "status", "submitted_at"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAgentApplicationDto(Object):
    user_id: str
    status: AgentApplicationStatus = AgentApplicationStatus.DRAFT


class UpdateAgentApplicationDto(Object):
    status: Optional[AgentApplicationStatus] = None
    types: Optional[List[AgentType]] = None
    kyc_method: Optional[KycMethod] = None
    bvn_last4: Optional[str] = None
    bvn_verification_id: Optional[str] = None
    bvn_verified_at: Optional[datetime] = None
    id_doc_type: Optional[IdDocType] = None
    id_doc_url: Optional[str] = None
    selfie_url: Optional[str] = None
    selfie_match_score: Optional[int] = None
    selfie_matched_at: Optional[datetime] = None
    surveyor_licence_no: Optional[str] = None
    surveyor_licence_url: Optional[str] = None
    nba_licence_no: Optional[str] = None
    nba_licence_url: Optional[str] = None
    years_of_experience: Optional[int] = None
    coverage_states: Optional[List[str]] = None
    coverage_lgas: Optional[List[str]] = None
    bio: Optional[str] = None
    truthfulness_acknowledged: Optional[str] = None
    agent_terms_consent_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_by_admin_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class SearchAgentApplicationDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class QueryAgentApplicationDto(BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None
    types: Optional[List[str]] = None
    submitted_at: Optional[datetime] = None
    reviewed_by_admin_id: Optional[str] = None


# ─── Public step DTOs (input) ─────────────────────────────────────

class TypesStepDto(Object):
    types: List[AgentType]


class BvnVerifyDto(Object):
    bvn: str  # 11 digits


class KycDocumentsDto(Object):
    id_doc_type: IdDocType
    id_doc_url: str  # presigned-uploaded URL
    selfie_url: str


class CredentialsStepDto(Object):
    surveyor_licence_no: Optional[str] = None
    surveyor_licence_url: Optional[str] = None
    nba_licence_no: Optional[str] = None
    nba_licence_url: Optional[str] = None
    years_of_experience: Optional[int] = None
    coverage_states: List[str]
    coverage_lgas: List[str]
    bio: Optional[str] = None


class SubmitApplicationDto(Object):
    truthfulness_acknowledged: bool
    agent_terms_consent_version: str


class ApproveApplicationDto(Object):
    note: Optional[str] = None


class RejectApplicationDto(Object):
    reason: str  # ≥ 30 chars enforced in validator


# ─── Public response DTO ──────────────────────────────────────────

class AgentApplicationDto(Object):
    id: str
    user_id: str
    status: AgentApplicationStatus
    types: List[AgentType]
    kyc_method: Optional[KycMethod] = None
    bvn_last4: Optional[str] = None
    bvn_verified_at: Optional[datetime] = None
    id_doc_type: Optional[IdDocType] = None
    id_doc_uploaded: bool = False
    selfie_uploaded: bool = False
    selfie_match_score: Optional[int] = None
    surveyor_licence_no: Optional[str] = None
    nba_licence_no: Optional[str] = None
    years_of_experience: Optional[int] = None
    coverage_states: List[str] = []
    coverage_lgas: List[str] = []
    bio: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Admin-facing DTO — exposes signed URLs (admins only).
class AdminAgentApplicationDto(AgentApplicationDto):
    id_doc_url: Optional[str] = None
    selfie_url: Optional[str] = None
    surveyor_licence_url: Optional[str] = None
    nba_licence_url: Optional[str] = None
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_email: Optional[str] = None


class BvnVerificationResultDto(Object):
    verified: bool
    bvn_last4: str
    verification_id: Optional[str] = None
    failure_reason: Optional[str] = None


class KycUploadUrlsDto(Object):
    """Returned by the start-of-step-2 endpoint so the frontend can PUT
    files directly to S3 with short-lived presigned URLs."""
    id_doc_upload_url: str
    id_doc_object_key: str
    selfie_upload_url: str
    selfie_object_key: str
    expires_in_seconds: int
