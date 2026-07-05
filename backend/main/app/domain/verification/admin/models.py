"""Admin verification control-panel DTOs (PRD §6.1).

Orchestration-only module — no ORM entity of its own. Composes the verification
aggregate, its tasks, property, admin notes, payments, commissions, and chargebacks
into the admin list + detail views, and carries the action request shapes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from main.app.core.sla import SlaHealth  # re-exported: single SLA-health source (core/sla)
from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.commission.models import CommissionDto
from main.app.domain.payment.chargeback.models import ChargebackDto
from main.app.domain.payment.models import PaymentDto
from main.app.domain.property.models import PropertyDto
from main.app.domain.verification.admin_note.models import AdminNoteDto
from main.app.domain.verification.task.models import TaskDto
from main.appodus_utils import Object


class VerificationSummaryDto(Object):
    """Row in the admin verifications list."""

    id: str
    vid: str
    customer_id: str
    tier: Optional[VerificationTier] = None
    status: VerificationStatus
    paused: bool = False
    state_region: Optional[str] = None
    sla_due_date: Optional[date] = None
    sla_health: SlaHealth = SlaHealth.NONE
    business_days_remaining: Optional[int] = None
    date_created: datetime


class VerificationDetailDto(Object):
    """Full admin detail view: aggregate + per-role task grid + related records."""

    summary: VerificationSummaryDto
    property: Optional[PropertyDto] = None
    tasks: List[TaskDto] = []
    notes: List[AdminNoteDto] = []
    payments: List[PaymentDto] = []
    commissions: List[CommissionDto] = []
    chargebacks: List[ChargebackDto] = []
    progress_percent: int = 0
    required_task_count: int = 0
    approved_task_count: int = 0


class AdminDashboardDto(Object):
    """Admin operations home summary (§6) — backend-owned queue health so the console
    renders counts without deriving anything client-side."""

    total: int = 0
    status_counts: Dict[VerificationStatus, int] = {}
    overdue: int = 0                    # active verifications past their SLA due date
    unassigned_pool_tasks: int = 0      # broadcast tasks unclaimed in the open pool
    pending_agent_applications: int = 0
    open_chargebacks: int = 0
    recent: List[VerificationSummaryDto] = []


# ── action request DTOs ───────────────────────────────────────────

class SetDelayDto(Object):
    """Graceful SLA shedding / manual extension (§6.4)."""

    extra_business_days: int
    reason: Optional[str] = None


class CancelVerificationDto(Object):
    reason: str
