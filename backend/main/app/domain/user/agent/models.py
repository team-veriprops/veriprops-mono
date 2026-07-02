"""Agent onboarding & KYC domain models (PRD §3.1–3.2, §3.3a).

An agent is a User with the AGENT persona plus an application profile, per-role
credentials (with structured expiry), and coverage. Application submission is a
resumable 4-step wizard; the draft lives in ``agent_application_drafts``.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Column, Date, Index, Integer, String, Text
from sqlalchemy.ext.mutable import MutableList

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT
from main.appodus_utils.integrations.kyc.models import (
    GovIdType,
    KycMethod,
    KycProvider,
    KycResultStatus,
)


class AgentApplicationStatus(str, enum.Enum):
    """Lifecycle of an agent application (PRD §3.1: PENDING → APPROVED/REJECTED)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CredentialType(str, enum.Enum):
    """Professional credentials with a natural expiry (PRD §3.1 step 3, §3.3a)."""

    SURVEYOR_LICENCE = "SURVEYOR_LICENCE"
    NBA_LICENCE = "NBA_LICENCE"


class CredentialStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    # Set when the credential's expiry_date has passed — the role it backs is
    # suspended (role-level, not account-level, PRD §3.3a).
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


# The credential each role requires before it can be approved / stay active
# (PRD §3.1 step 3). Roles absent here need no professional licence.
ROLE_REQUIRED_CREDENTIAL = {
    AgentRole.SURVEYOR: CredentialType.SURVEYOR_LICENCE,
    AgentRole.LAWYER: CredentialType.NBA_LICENCE,
}


# ─── ORM ──────────────────────────────────────────────────────────

class AgentProfile(BaseEntity):
    __tablename__ = "agent_profiles"

    user_id = Column(String(36), nullable=False, index=True)
    # Roles the applicant is being reviewed for (PRD §3.1 step 1, multi-select).
    roles = Column(MutableList.as_mutable(JSONB_VARIANT), nullable=False, default=list)
    # Roles cleared by admin — the subset of ``roles`` the agent may work.
    approved_roles = Column(MutableList.as_mutable(JSONB_VARIANT), nullable=False, default=list)
    status = Column(String(16), nullable=False, default=AgentApplicationStatus.PENDING.value, index=True)
    rejection_reason = Column(String(500), nullable=True)
    bio = Column(String(300), nullable=True)
    years_experience = Column(Integer, nullable=True)
    submitted_at = Column(UTCDateTime, nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)
    reviewed_by = Column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_agent_profiles_status", "status"),
    )


class AgentCredential(BaseEntity):
    __tablename__ = "agent_credentials"

    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    credential_type = Column(String(32), nullable=False)
    licence_number = Column(String(64), nullable=True)
    # Encrypted-S3 object key for the uploaded credential document (access-controlled).
    document_ref = Column(String(512), nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(16), nullable=False, default=CredentialStatus.PENDING.value)


class AgentCoverage(BaseEntity):
    __tablename__ = "agent_coverage"

    user_id = Column(String(36), nullable=False, index=True)
    state = Column(String(64), nullable=False)
    lga = Column(String(64), nullable=True)
    place = Column(String(255), nullable=True)
    travel_radius_km = Column(Integer, nullable=True)


class AgentApplicationDraft(BaseEntity):
    """Resumable wizard state, one active draft per user (mirrors signup_drafts)."""

    __tablename__ = "agent_application_drafts"

    user_id = Column(String(36), nullable=False, index=True)
    step = Column(Integer, nullable=False, server_default="0")
    payload = Column(Text, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)


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


# ─── DTOs: drafts ─────────────────────────────────────────────────

class CreateAgentApplicationDraftDto(Object):
    user_id: str
    step: int = 0
    payload: str
    expires_at: datetime


class UpdateAgentApplicationDraftDto(Object):
    step: Optional[int] = None
    payload: Optional[str] = None


class SearchAgentApplicationDraftDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None


class QueryAgentApplicationDraftDto(BaseQueryDto):
    user_id: Optional[str] = None
    step: Optional[int] = None


class AgentApplicationDraftDto(Object):
    """Wizard draft as the frontend consumes it (payload parsed to an object)."""

    step: int
    payload: dict
    date_updated: Optional[datetime] = None


class SaveAgentApplicationDraftDto(Object):
    step: int
    payload: dict


# ─── DTOs: profile / credentials / coverage ───────────────────────

class CreateAgentProfileDto(Object):
    user_id: str
    roles: List[AgentRole]
    status: AgentApplicationStatus = AgentApplicationStatus.PENDING
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    submitted_at: Optional[datetime] = None


class UpdateAgentProfileDto(Object):
    roles: Optional[List[str]] = None
    approved_roles: Optional[List[str]] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    reviewed_by: Optional[str] = None


class SearchAgentProfileDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


class QueryAgentProfileDto(BaseQueryDto):
    user_id: Optional[str] = None
    roles: Optional[List[str]] = None
    approved_roles: Optional[List[str]] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None


class CreateAgentCredentialDto(Object):
    user_id: str
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    expiry_date: Optional[date] = None
    status: CredentialStatus = CredentialStatus.PENDING


class UpdateAgentCredentialDto(Object):
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    status: Optional[str] = None


class SearchAgentCredentialDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    role: Optional[str] = None


class QueryAgentCredentialDto(BaseQueryDto):
    user_id: Optional[str] = None
    role: Optional[str] = None
    credential_type: Optional[str] = None
    licence_number: Optional[str] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None


class CreateAgentCoverageDto(Object):
    user_id: str
    state: str
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


class UpdateAgentCoverageDto(Object):
    state: Optional[str] = None
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


class SearchAgentCoverageDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None


class QueryAgentCoverageDto(BaseQueryDto):
    user_id: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


# ─── DTOs: KYC record ─────────────────────────────────────────────

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

class AgentCoverageInputDto(Object):
    state: str
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


class AgentCredentialInputDto(Object):
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    expiry_date: Optional[date] = None


class KycSubmissionDto(Object):
    """KYC input at submission (PRD §3.1 step 2). BVN primary; gov-ID fallback."""

    method: KycMethod
    bvn: Optional[str] = None
    id_type: Optional[GovIdType] = None
    id_number: Optional[str] = None
    # Access-controlled S3 reference for the uploaded selfie/ID (never the bytes).
    selfie_reference: Optional[str] = None
    document_ref: Optional[str] = None


class SubmitAgentApplicationDto(Object):
    """Final wizard submission (PRD §3.1 step 4)."""

    roles: List[AgentRole]
    kyc: KycSubmissionDto
    credentials: List[AgentCredentialInputDto] = []
    coverage: List[AgentCoverageInputDto] = []
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    truthfulness_confirmed: bool
    agent_terms_version: str


class AgentCredentialDto(Object):
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    expiry_date: Optional[date] = None
    status: CredentialStatus


class KycRecordDto(Object):
    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    score: Optional[int] = None
    summary: Optional[str] = None
    verified_at: Optional[datetime] = None


class AgentApplicationStatusDto(Object):
    """The applicant's own view (PRD §3.1 Approval Status Dashboard)."""

    status: AgentApplicationStatus
    roles: List[AgentRole]
    approved_roles: List[AgentRole]
    active_roles: List[AgentRole]
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None


class AgentApplicationSummaryDto(Object):
    """Row in the admin applications DataTable."""

    id: str
    user_id: str
    applicant_name: str
    roles: List[AgentRole]
    status: AgentApplicationStatus
    submitted_at: Optional[datetime] = None


class AgentApplicationDetailDto(Object):
    """Admin DetailDrawer view of a single application."""

    id: str
    user_id: str
    applicant_name: str
    applicant_email: str
    roles: List[AgentRole]
    approved_roles: List[AgentRole]
    status: AgentApplicationStatus
    rejection_reason: Optional[str] = None
    bio: Optional[str] = None
    years_experience: Optional[int] = None
    submitted_at: Optional[datetime] = None
    credentials: List[AgentCredentialDto] = []
    coverage: List[AgentCoverageInputDto] = []
    kyc: Optional[KycRecordDto] = None


class ApproveAgentApplicationDto(Object):
    # Subset of applied roles to approve; empty ⇒ approve all applied roles.
    approved_roles: Optional[List[AgentRole]] = None


class RejectAgentApplicationDto(Object):
    reason: str
