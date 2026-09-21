"""Admin verification control-panel controller (PRD §6.1).

URL shape: /admin/verifications/... — mounted at the domain root. Every route is
RBAC-gated: list/detail/notes/lifecycle need MANAGE_VERIFICATIONS; agent assignment
needs ASSIGN_AGENT. Frontend service: frontend/src/services/admin-verification-service.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.core.state.status import AgentRole
from main.app.domain.payment.chargeback.models import ChargebackDto, ResolveChargebackDto
from main.app.domain.payment.chargeback.service import ChargebackService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.admin.models import (
    AdminDashboardDto,
    CancelVerificationDto,
    SetDelayDto,
    VerificationDetailDto,
    VerificationSummaryDto,
)
from main.app.domain.verification.admin.service import AdminVerificationService
from main.app.domain.verification.admin_note.models import AddAdminNoteDto
from main.app.domain.verification.task.models import AssignTaskDto
from main.appodus_utils.db.models import Page, SuccessResponse

admin_verification_router = APIRouter(prefix="/admin/verifications", tags=["Admin: Verifications"])
admin_service: AdminVerificationService = di[AdminVerificationService]
chargeback_service: ChargebackService = di[ChargebackService]


def _cb_dto(c) -> ChargebackDto:
    from main.app.domain.payment.chargeback.models import ChargebackStatus
    from main.appodus_utils.db.types.money import TransactionCurrency
    return ChargebackDto(
        id=c.id, payment_id=c.payment_id, verification_id=c.verification_id,
        status=ChargebackStatus(c.status), reason=c.reason, amount_minor=c.amount_minor,
        currency=TransactionCurrency(c.currency), rebuttal_pack=c.rebuttal_pack,
        resolved_at=c.resolved_at, date_created=c.date_created,
    )


# ── List & detail (§6.1) ──────────────────────────────────────────

@admin_verification_router.get("", response_model=SuccessResponse[Page[VerificationSummaryDto]])
async def list_verifications(
    status: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    state_region: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    overdue_only: bool = Query(default=False),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    result = await admin_service.list_verifications(
        status=status, tier=tier, state_region=state_region, query=query,
        overdue_only=overdue_only, page=page, page_size=page_size,
    )
    return SuccessResponse[Page[VerificationSummaryDto]](data=result)


@admin_verification_router.get("/summary", response_model=SuccessResponse[AdminDashboardDto])
async def get_dashboard_summary(
    _admin_id: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    """Admin operations home summary (§6). Registered before ``/{verification_id}`` so the
    literal path wins over the path-param route."""
    return SuccessResponse[AdminDashboardDto](data=await admin_service.summary())


@admin_verification_router.get("/{verification_id}", response_model=SuccessResponse[VerificationDetailDto])
async def get_detail(
    verification_id: str,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.get_detail(verification_id))


# ── Assignment (§6.3) ─────────────────────────────────────────────

@admin_verification_router.post(
    "/{verification_id}/tasks/{role}/assign", response_model=SuccessResponse[VerificationDetailDto]
)
async def assign_agent(
    verification_id: str,
    role: AgentRole,
    req: AssignTaskDto,
    admin_id: str = Depends(require_permission(Permission.ASSIGN_AGENT)),
):
    detail = await admin_service.assign(verification_id, role, req.agent_id, admin_id)
    return SuccessResponse[VerificationDetailDto](data=detail)


# ── Lifecycle actions (§6.1) ──────────────────────────────────────

@admin_verification_router.post("/{verification_id}/pause", response_model=SuccessResponse[VerificationDetailDto])
async def pause(verification_id: str, admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS))):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.pause(verification_id, admin_id))


@admin_verification_router.post("/{verification_id}/resume", response_model=SuccessResponse[VerificationDetailDto])
async def resume(verification_id: str, admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS))):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.resume(verification_id, admin_id))


@admin_verification_router.post("/{verification_id}/cancel", response_model=SuccessResponse[VerificationDetailDto])
async def cancel(
    verification_id: str,
    req: CancelVerificationDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.cancel(verification_id, req, admin_id))


@admin_verification_router.post("/{verification_id}/delay", response_model=SuccessResponse[VerificationDetailDto])
async def set_delay(
    verification_id: str,
    req: SetDelayDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.set_delay(verification_id, req, admin_id))


@admin_verification_router.post("/{verification_id}/notes", response_model=SuccessResponse[VerificationDetailDto])
async def add_note(
    verification_id: str,
    req: AddAdminNoteDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[VerificationDetailDto](data=await admin_service.add_note(verification_id, req, admin_id))


# ── Timeout sweeps (§11.4) — manual/deterministic trigger ──────────

@admin_verification_router.post("/sweeps/no-show", response_model=SuccessResponse[dict])
async def sweep_no_show(
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Reclaim manually-assigned tasks the agent never accepted in time (§11.4). Runs
    on a schedule in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.verification.task.service import VerificationTaskService
    reclaimed = await di[VerificationTaskService].sweep_no_show()
    return SuccessResponse[dict](data={"reclaimed": reclaimed})


@admin_verification_router.post("/sweeps/pool-starvation", response_model=SuccessResponse[dict])
async def sweep_pool_starvation(
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Escalate broadcast tasks unclaimed past the pool timeout off the open pool (§11.4)."""
    from main.app.domain.verification.task.service import VerificationTaskService
    escalated = await di[VerificationTaskService].sweep_pool_starvation()
    return SuccessResponse[dict](data={"escalated": escalated})


@admin_verification_router.post("/sweeps/sla-breach", response_model=SuccessResponse[dict])
async def sweep_sla_breach(
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Publish an SLA-breach notification for each newly-overdue verification (§12.2, D23).
    Runs on a schedule in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.verification.sla_monitor import SlaMonitorService
    flagged = await di[SlaMonitorService].sweep_sla_breaches()
    return SuccessResponse[dict](data={"flagged": flagged})


@admin_verification_router.post("/sweeps/abandonment", response_model=SuccessResponse[dict])
async def sweep_abandonment(
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Fire a one-time recovery email for each unpaid verification untouched for 24h (§17.1).
    Runs on a schedule in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.verification.service import VerificationService
    reminded = await di[VerificationService].sweep_abandoned_drafts()
    return SuccessResponse[dict](data={"reminded": reminded})


@admin_verification_router.post("/sweeps/referral-credits", response_model=SuccessResponse[dict])
async def sweep_referral_credits(
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Clear referral credits past their chargeback window into referrer balances (§17.1).
    Runs on a schedule in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.referral.service import ReferralService
    cleared = await di[ReferralService].sweep_referral_credits()
    return SuccessResponse[dict](data={"cleared": cleared})


# ── Chargeback sub-process (§6a) ──────────────────────────────────

@admin_verification_router.post(
    "/chargebacks/{chargeback_id}/rebuttal", response_model=SuccessResponse[ChargebackDto]
)
async def submit_rebuttal(
    chargeback_id: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    cb = await chargeback_service.submit_rebuttal(chargeback_id, admin_id)
    return SuccessResponse[ChargebackDto](data=_cb_dto(cb))


@admin_verification_router.post(
    "/chargebacks/{chargeback_id}/resolve", response_model=SuccessResponse[ChargebackDto]
)
async def resolve_chargeback(
    chargeback_id: str,
    req: ResolveChargebackDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    cb = await chargeback_service.resolve(chargeback_id, req.won, admin_id)
    return SuccessResponse[ChargebackDto](data=_cb_dto(cb))
