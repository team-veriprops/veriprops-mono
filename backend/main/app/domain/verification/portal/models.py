"""Portal-facing DTOs — customer tracking, evidence, and report views (S32–S36)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from main.appodus_utils import Object


# ── Tracking (S32) ──────────────────────────────────────────────────────────

class AssignedAgentDto(Object):
    role: str
    first_name: str
    is_trusted: bool


class SlaDto(Object):
    started_at: Optional[datetime] = None
    target_days: int
    elapsed_days: int
    on_track: bool


class TrackingDto(Object):
    verification_id: str
    vid: str
    status: str
    status_label: str
    status_detail: str
    progress_pct: int
    tier: str
    property_address: Optional[str] = None
    assigned_agents: List[AssignedAgentDto] = []
    sla: Optional[SlaDto] = None
    trust_score: Optional[Decimal] = None


# ── Evidence (S34) ──────────────────────────────────────────────────────────

class CustomerEvidenceItemDto(Object):
    id: str
    evidence_type: str
    file_url: str
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    captured_at: Optional[datetime] = None
    agent_role: str


# ── Report acknowledgement (S35) ─────────────────────────────────────────────

class AcknowledgeDto(Object):
    ip_address: Optional[str] = None


# ── Dashboard summary ─────────────────────────────────────────────────────────

class AbandonedVerificationSummaryDto(Object):
    id: str
    vid: str
    tier: str
    status: str
    property_state: Optional[str] = None
    property_lga: Optional[str] = None
    property_address: Optional[str] = None
    total_amount_minor: Optional[int] = None
    currency: Optional[str] = None
    date_updated: Optional[datetime] = None
    date_created: datetime


class DashboardSummaryDto(Object):
    total: int
    active: int
    completed: int
    unread_report_count: int
    abandoned: List[AbandonedVerificationSummaryDto]
