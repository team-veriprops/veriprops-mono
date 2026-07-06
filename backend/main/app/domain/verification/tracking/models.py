"""Customer tracking & evidence DTOs (PRD §9). Orchestration-only — no ORM entity.

Every DTO here is customer-facing, so agent identity is reduced to the four safe fields
(§4.9/§9.5) and interim signal is admin-review-gated (§9.3).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from main.app.core.sla import SlaHealth
from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.verification.task.evidence.models import EvidenceKind
from main.appodus_utils import BaseQueryDto, Object, PageRequest


class AssignedAgentDto(Object):
    """An assigned agent as the customer may see them — first name + role only (§4.9).

    Deliberately omits last name, email, phone and any contact handle. This is the
    API-level enforcement of the first-name-only rule (§9.5 exit criterion)."""

    role: AgentRole
    first_name: str
    avatar_url: Optional[str] = None
    verified: bool = False


class TrackingTaskDto(Object):
    """A per-role step in the customer progress tracker (§9.1), collapsed to the
    customer-facing three-state label (§9.2)."""

    role: AgentRole
    # Customer-facing label: Pending / In Progress / Completed, or "Awaiting other
    # stages" for a dependency-blocked Lawyer row.
    state_label: str
    completed: bool = False
    locked: bool = False  # dependency-blocked (Lawyer awaiting siblings)
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class InterimMilestoneDto(Object):
    """A positive, provisional interim reassurance surfaced after admin review-approval
    (§9.3). Risk-bearing findings are withheld until review, so only approved tasks
    produce a milestone."""

    role: AgentRole
    message: str  # provisional positive copy, e.g. "Registry check complete — so far, no issues found"
    note: Optional[str] = None  # optional one-line admin note
    at: Optional[datetime] = None


class CustomerEvidenceDto(Object):
    """A single tamper-evident evidence item in the customer feed (§9.4), tagged by role
    not agent name, with a short-lived presigned URL and its content hash / server GPS."""

    id: str
    role: AgentRole
    kind: EvidenceKind
    url: Optional[str] = None  # presigned; regenerated on each read
    mime_type: Optional[str] = None
    content_sha256: str
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    captured_at: Optional[datetime] = None
    uploaded_at: datetime


class SlaTrackerDto(Object):
    """SLA countdown surfaced to the customer (§9.1)."""

    expected_date: Optional[date] = None
    health: SlaHealth = SlaHealth.NONE
    label: Optional[str] = None  # On track / Running late / Delayed
    business_days_remaining: Optional[int] = None
    elapsed_business_days: Optional[int] = None
    total_business_days: Optional[int] = None


class VerificationTrackingDto(Object):
    """The single shared tracking snapshot (§9.1) — the body of both the 60s poll
    response and the SSE stream's initial frame."""

    id: str
    vid: str
    tier: Optional[VerificationTier] = None
    status: VerificationStatus
    status_label: str
    address: Optional[str] = None
    paused: bool = False
    paid_at: Optional[datetime] = None
    sla: SlaTrackerDto = SlaTrackerDto()
    progress_percent: int = 0
    required_task_count: int = 0
    approved_task_count: int = 0
    tasks: List[TrackingTaskDto] = []
    agents: List[AssignedAgentDto] = []
    interim_milestones: List[InterimMilestoneDto] = []
    evidence_preview: List[CustomerEvidenceDto] = []


class CustomerEvidenceQueryDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None


class VerificationListItemDto(Object):
    """A row in the customer's 'My Verifications' list (§9)."""

    id: str
    vid: str
    tier: Optional[VerificationTier] = None
    status: VerificationStatus
    status_label: str
    address: Optional[str] = None
    sla_due_date: Optional[date] = None
    date_created: datetime


class ResumableDraftDto(Object):
    """The customer's most recent still-completable verification, backing the §17.1
    abandonment-recovery banner. ``needs_payment`` routes the CTA to pay vs. the wizard."""

    id: str
    vid: str
    status: VerificationStatus
    tier: Optional[VerificationTier] = None
    draft_step: int = 0
    needs_payment: bool = False


class CustomerDashboardDto(Object):
    """The customer portal home summary (§9) — backend-owned rollups over the
    customer's verifications plus the most recent rows. Every count is derived here so
    the client renders numbers, never computes them."""

    total: int = 0
    draft: int = 0            # DRAFT — awaiting submission
    awaiting_payment: int = 0  # SUBMITTED / PAYMENT_PENDING
    in_progress: int = 0       # PAID / IN_PROGRESS / UNDER_REVIEW — work underway
    completed: int = 0         # COMPLETED — report released
    status_counts: Dict[VerificationStatus, int] = {}
    recent: List[VerificationListItemDto] = []
    # The most recent unpaid verification the customer can resume (§17.1). None when
    # nothing is pending — the recovery banner only shows when this is set.
    resumable_draft: Optional[ResumableDraftDto] = None
