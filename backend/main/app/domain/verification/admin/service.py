"""Admin verification control-panel service (PRD §6.1–§6.4).

Orchestrates the admin's view of and actions on verifications: the filtered list
with SLA health, the composed detail, agent assignment (delegated to the task
service, which owns the derivation), and the operational actions — pause/resume
(a flag, never a state), cancel, SLA delay/shedding, and admin notes. Every action
is audit-logged.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.core.sla import ACTIVE_SLA_STATES, SlaHealth, add_business_days, compute_sla_health
from main.app.core.state.dependencies import required_task_count
from main.app.core.state.machine import verification_state_machine
from main.app.core.state.status import (
    AgentRole,
    TaskState,
    VerificationStatus,
    VerificationTier,
)
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.models import CommissionDto, CommissionStatus
from main.app.domain.commission.service import CommissionService
from main.app.domain.payment.chargeback.models import ChargebackDto, ChargebackStatus
from main.app.domain.payment.chargeback.service import ChargebackService
from main.app.domain.payment.models import PaymentDto, PaymentMethodKind, PaymentStatus
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.property.models import PropertyDto, PropertyType
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.user.agent.service import AgentService
from main.app.domain.verification.admin.models import (
    AdminDashboardDto,
    CancelVerificationDto,
    SetDelayDto,
    VerificationDetailDto,
    VerificationSummaryDto,
)
from main.app.domain.verification.admin_note.models import AddAdminNoteDto, AdminNoteDto
from main.app.domain.verification.admin_note.service import AdminNoteService
from main.app.domain.verification.models import Verification
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.models import TaskAssignmentMode, TaskDto
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)

# Number of most-recent verifications surfaced on the admin dashboard.
_DASHBOARD_RECENT_LIMIT = 8
# Active verifications due within this many days count as SLA-at-risk (§18.1 Mission Control).
_SLA_AT_RISK_DAYS = 2


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminVerificationService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        property_repo: PropertyRepo,
        payment_repo: PaymentRepo,
        task_service: VerificationTaskService,
        admin_note_service: AdminNoteService,
        commission_service: CommissionService,
        chargeback_service: ChargebackService,
        agent_service: AgentService,
        audit_service: AuditLogService,
    ):
        self._repo = verification_repo
        self._property_repo = property_repo
        self._payment_repo = payment_repo
        self._task_service = task_service
        self._notes = admin_note_service
        self._commissions = commission_service
        self._chargebacks = chargeback_service
        self._agents = agent_service
        self._audit = audit_service

    # ── Dashboard summary (§6) ────────────────────────────────────

    async def summary(self) -> AdminDashboardDto:
        """Admin operations home rollups (§6): queue counts by status, overdue count,
        open pool tasks, pending agent applications, open chargebacks, and the most
        recent verifications. Every figure is derived here (backend source of truth)."""
        raw = await self._repo.count_by_status()
        status_counts = {VerificationStatus(s): c for s, c in raw.items()}
        today = Utils.datetime_now().date()
        horizon = today + timedelta(days=_SLA_AT_RISK_DAYS)
        recent_rows, _ = await self._repo.page_admin(offset=0, limit=_DASHBOARD_RECENT_LIMIT)
        return AdminDashboardDto(
            total=sum(status_counts.values()),
            status_counts=status_counts,
            overdue=await self._repo.count_overdue(list(ACTIVE_SLA_STATES), today),
            sla_at_risk=await self._repo.count_due_within(list(ACTIVE_SLA_STATES), today, horizon),
            unassigned_pool_tasks=await self._task_service.count_pool_pending(),
            pending_agent_applications=await self._agents.count_pending_applications(),
            open_chargebacks=await self._chargebacks.count_open(),
            available_agents=await self._agents.count_available_agents(),
            revenue_minor=await self._payment_repo.sum_succeeded_amount(),
            recent=[await self._summary(v) for v in recent_rows],
        )

    # ── List (§6.1) ───────────────────────────────────────────────

    async def list_verifications(
        self,
        *,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        state_region: Optional[str] = None,
        query: Optional[str] = None,
        overdue_only: bool = False,
        page: int = 0,
        page_size: int = 10,
    ) -> Page[VerificationSummaryDto]:
        due_before = Utils.datetime_now().date() if overdue_only else None
        rows, total = await self._repo.page_admin(
            status=status, tier=tier, state_region=state_region, query=query,
            due_before=due_before, offset=page * page_size, limit=page_size,
        )
        items = [await self._summary(v) for v in rows]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[VerificationSummaryDto](
            items=items,
            meta=PaginationMeta(
                page=page, page_size=page_size, count=len(items), total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    # ── Detail (§6.1) ─────────────────────────────────────────────

    async def get_detail(self, verification_id: str) -> VerificationDetailDto:
        verification = await self._get(verification_id)
        tasks = await self._task_service.list_for_verification(verification_id)
        notes = await self._notes.list_for_verification(verification_id)
        payments = await self._payment_repo.list_for_verification(verification_id)
        commissions = await self._commissions.list_for_verification(verification_id)
        chargebacks = await self._chargebacks.list_for_verification(verification_id)

        prop = None
        if verification.property_id:
            prop = await self._property_repo.get_model(verification.property_id)

        required = required_task_count(VerificationTier(verification.tier)) if verification.tier else 0
        approved = sum(1 for t in tasks if t.state == TaskState.APPROVED.value)
        progress = int((approved / required) * 100) if required else 0

        return VerificationDetailDto(
            summary=await self._summary(verification),
            property=self._property_dto(prop),
            tasks=[self._task_dto(t) for t in tasks],
            notes=[self._note_dto(n) for n in notes],
            payments=[self._payment_dto(p) for p in payments],
            commissions=[self._commission_dto(c) for c in commissions],
            chargebacks=[self._chargeback_dto(c) for c in chargebacks],
            progress_percent=progress,
            required_task_count=required,
            approved_task_count=approved,
        )

    # ── Actions (§6.1/§6.3/§6.4) ──────────────────────────────────

    async def assign(
        self, verification_id: str, role: AgentRole, agent_id: str, admin_id: str
    ) -> VerificationDetailDto:
        await self._task_service.assign(verification_id, role, agent_id, admin_id)
        return await self.get_detail(verification_id)

    async def pause(self, verification_id: str, admin_id: str) -> VerificationDetailDto:
        verification = await self._get(verification_id)
        verification.paused = True  # bool False can't round-trip the exclude_none update path
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_PAUSED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
        )
        return await self.get_detail(verification_id)

    async def resume(self, verification_id: str, admin_id: str) -> VerificationDetailDto:
        verification = await self._get(verification_id)
        verification.paused = False
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_RESUMED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
        )
        return await self.get_detail(verification_id)

    async def cancel(
        self, verification_id: str, dto: CancelVerificationDto, admin_id: str
    ) -> VerificationDetailDto:
        verification = await self._get(verification_id)
        verification_state_machine.assert_can_transition(
            verification.status, VerificationStatus.CANCELLED.value, resource="Verification"
        )
        await self._repo.update(
            verification_id,
            {"status": VerificationStatus.CANCELLED.value},
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_CANCELLED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
            from_state=verification.status, to_state=VerificationStatus.CANCELLED.value,
            details={"reason": dto.reason, "refund_pending": True},  # refund executes in S12
        )
        return await self.get_detail(verification_id)

    async def set_delay(
        self, verification_id: str, dto: SetDelayDto, admin_id: str
    ) -> VerificationDetailDto:
        verification = await self._get(verification_id)
        if not verification.sla_due_date:
            raise InvalidResourceStateException(
                resource="verification", message="No SLA clock to extend yet."
            )
        old_due = verification.sla_due_date
        verification.sla_due_date = add_business_days(old_due, dto.extra_business_days)
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_DELAYED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
            details={"extra_business_days": dto.extra_business_days, "reason": dto.reason,
                     "old_due": old_due.isoformat(), "new_due": verification.sla_due_date.isoformat()},
        )
        return await self.get_detail(verification_id)

    async def add_note(
        self, verification_id: str, dto: AddAdminNoteDto, admin_id: str
    ) -> VerificationDetailDto:
        await self._get(verification_id)
        note = await self._notes.add(verification_id, admin_id, dto)
        self._audit.schedule(
            action=AuditActionType.ADMIN_NOTE_ADDED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
            details={"note_id": note.id, "category": dto.category.value},
        )
        return await self.get_detail(verification_id)

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, verification_id: str) -> Verification:
        verification = await self._repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        return verification

    async def _summary(self, v: Verification) -> VerificationSummaryDto:
        health, remaining = self._sla_health(v)
        state_region = None
        if v.property_id:
            prop = await self._property_repo.get_model(v.property_id)
            state_region = prop.state if prop else None
        return VerificationSummaryDto(
            id=v.id, vid=v.vid, customer_id=v.customer_id,
            tier=VerificationTier(v.tier) if v.tier else None,
            status=VerificationStatus(v.status), paused=bool(v.paused),
            state_region=state_region, sla_due_date=v.sla_due_date,
            sla_health=health, business_days_remaining=remaining,
            date_created=v.date_created,
        )

    def _sla_health(self, v: Verification) -> tuple[SlaHealth, Optional[int]]:
        return compute_sla_health(v.status, v.sla_due_date, Utils.datetime_now().date())

    def _property_dto(self, p) -> Optional[PropertyDto]:
        if not p:
            return None
        return PropertyDto(
            id=p.id, property_type=PropertyType(p.property_type), address=p.address,
            landmark=p.landmark, state=p.state, lga=p.lga,
            latitude=p.latitude, longitude=p.longitude,
        )

    def _task_dto(self, t) -> TaskDto:
        return TaskDto(
            id=t.id, verification_id=t.verification_id, role=AgentRole(t.role),
            tier=VerificationTier(t.tier), state=TaskState(t.state),
            assigned_agent_id=t.assigned_agent_id,
            assignment_mode=TaskAssignmentMode(t.assignment_mode) if t.assignment_mode else None,
            in_pool=bool(t.in_pool), pool_expires_at=t.pool_expires_at,
            accept_deadline_at=t.accept_deadline_at, decline_count=t.decline_count or 0,
            remote_bonus_minor=t.remote_bonus_minor, assigned_at=t.assigned_at,
            accepted_at=t.accepted_at, submitted_at=t.submitted_at, approved_at=t.approved_at,
        )

    def _note_dto(self, n) -> AdminNoteDto:
        from main.app.domain.verification.admin_note.models import AdminNoteCategory
        return AdminNoteDto(
            id=n.id, verification_id=n.verification_id, author_id=n.author_id,
            category=AdminNoteCategory(n.category), body=n.body, pinned=bool(n.pinned),
            date_created=n.date_created,
        )

    def _payment_dto(self, p) -> PaymentDto:
        return PaymentDto(
            id=p.id, verification_id=p.verification_id, tx_ref=p.tx_ref,
            method=PaymentMethodKind(p.method), status=PaymentStatus(p.status),
            amount_minor=p.amount_minor, currency=TransactionCurrency(p.currency),
            charge_currency=TransactionCurrency(p.charge_currency) if p.charge_currency else None,
            charge_amount_minor=p.charge_amount_minor, checkout_url=p.checkout_url,
            date_created=p.date_created,
        )

    def _commission_dto(self, c) -> CommissionDto:
        return CommissionDto(
            id=c.id, verification_id=c.verification_id, task_id=c.task_id, agent_id=c.agent_id,
            role=AgentRole(c.role), tier=VerificationTier(c.tier), amount_minor=c.amount_minor,
            currency=TransactionCurrency(c.currency),
            status=CommissionStatus(c.status),
            clearing_until=c.clearing_until, date_created=c.date_created,
        )

    def _chargeback_dto(self, c) -> ChargebackDto:
        return ChargebackDto(
            id=c.id, payment_id=c.payment_id, verification_id=c.verification_id,
            status=ChargebackStatus(c.status), reason=c.reason, amount_minor=c.amount_minor,
            currency=TransactionCurrency(c.currency), rebuttal_pack=c.rebuttal_pack,
            resolved_at=c.resolved_at, date_created=c.date_created,
        )
