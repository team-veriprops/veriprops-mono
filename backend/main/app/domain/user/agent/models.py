"""Agent onboarding cross-entity DTOs (PRD §3.1–3.2).

The agent onboarding flow spans several single-entity child domains
(``profile``, ``credential``, ``coverage``, ``application_draft``, ``kyc``).
This module holds only the *orchestration* DTOs that compose those child domains
into the wizard submission and the admin review views — it declares no ORM entity.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.coverage.models import AgentCoverageInputDto
from main.app.domain.user.agent.credential.models import (
    AgentCredentialDto,
    AgentCredentialInputDto,
)
from main.app.domain.user.agent.kyc.models import KycRecordDto, KycSubmissionDto
from main.app.domain.user.agent.profile.models import AgentApplicationStatus
from main.appodus_utils import Object


# ─── Applicant: wizard submission ─────────────────────────────────

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


# ─── Applicant: status view ───────────────────────────────────────

class AgentApplicationStatusDto(Object):
    """The applicant's own view (PRD §3.1 Approval Status Dashboard)."""

    status: AgentApplicationStatus
    roles: List[AgentRole]
    approved_roles: List[AgentRole]
    active_roles: List[AgentRole]
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None


# ─── Admin: approval queue & detail ───────────────────────────────

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
