"""Dispute service (PRD §14.3).

A customer contests a completed report within the dispute window. Opening moves the
verification COMPLETED → DISPUTED and freezes related commissions (§15.2). When a dispute
targets an agent's task the agent is notified and may defend, admin-mediated, before the admin
resolves — the agent never learns the customer's identity. The admin resolves with one of three
outcomes, delivering a mandatory note verbatim to the customer:

- reject → COMPLETED (commissions unfrozen);
- uphold, full refund → REFUNDED (refund + commissions reversed);
- uphold, partial + free re-check → IN_PROGRESS (scoped tasks reopened; report → v2.0).
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.machine import verification_state_machine
from main.app.core.state.status import (
    AgentRole,
    ReportRevisionKind,
    VerificationStatus,
)
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.service import CommissionService
from main.app.domain.payment.service import PaymentService
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.verification.dispute.models import (
    CreateDisputeDto,
    Dispute,
    DisputeOutcome,
    DisputeStatus,
    OpenDisputeDto,
    ResolveDisputeDto,
    UpdateDisputeDto,
    dispute_to_dto,
)
from main.app.domain.verification.dispute.repo import DisputeRepo
from main.app.domain.verification.models import UpdateVerificationDto
from main.app.domain.verification.report.service import ReportService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.review.service import ReviewService
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_MIN_DESCRIPTION_CHARS = 100  # §14.3


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class DisputeService:
    def __init__(
        self,
        dispute_repo: DisputeRepo,
        verification_service: VerificationService,
        verification_repo: VerificationRepo,
        report_service: ReportService,
        review_service: ReviewService,
        commission_service: CommissionService,
        payment_service: PaymentService,
        config_service: ConfigService,
        task_repo: VerificationTaskRepo,
        audit_service: AuditLogService,
    ):
        self._repo = dispute_repo
        self._verifications = verification_service
        self._verification_repo = verification_repo
        self._reports = report_service
        self._reviews = review_service
        self._commissions = commission_service
        self._payments = payment_service
        self._config = config_service
        self._tasks = task_repo
        self._audit = audit_service

    async def open(self, verification_id: str, customer_id: str, dto: OpenDisputeDto) -> Dispute:
        """Open a dispute within the window (§14.3): COMPLETED → DISPUTED + freeze commissions."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        if v.status != VerificationStatus.COMPLETED.value:
            raise InvalidResourceStateException(
                resource="verification", message="Only a completed verification can be disputed."
            )
        if len((dto.description or "").strip()) < _MIN_DESCRIPTION_CHARS:
            raise ValidationException(
                message=f"Please describe the issue in at least {_MIN_DESCRIPTION_CHARS} characters."
            )
        await self._assert_within_window(verification_id)

        verification_state_machine.assert_can_transition(
            v.status, VerificationStatus.DISPUTED.value, resource="Verification"
        )
        await self._verification_repo.update(
            verification_id, UpdateVerificationDto(status=VerificationStatus.DISPUTED.value)
        )
        # High-stakes: freeze related clearing commissions until resolution (§15.2).
        await self._commissions.freeze_for_verification(verification_id, customer_id)

        agent_id: Optional[str] = None
        if dto.target_role is not None:
            task = await self._tasks.get_by_role(verification_id, dto.target_role.value)
            agent_id = task.assigned_agent_id if task else None

        dispute = await self._repo.create_return_model(CreateDisputeDto(
            verification_id=Utils.uuid_to_hex(v.id),
            customer_id=customer_id,
            dispute_type=dto.dispute_type,
            description=dto.description.strip(),
            evidence=dto.evidence,
            target_role=dto.target_role,
            agent_id=agent_id,
            status=DisputeStatus.OPEN,
        ))
        if agent_id and dto.target_role is not None:
            await self._notify_agent_defence(verification_id, agent_id, dto.target_role, dispute)

        self._audit.schedule(
            action=AuditActionType.DISPUTE_OPENED,
            resource_type="dispute", resource_id=dispute.id, actor_id=customer_id,
            from_state=VerificationStatus.COMPLETED.value, to_state=VerificationStatus.DISPUTED.value,
            details={"verification_id": verification_id, "type": dto.dispute_type.value,
                     "target_role": dto.target_role.value if dto.target_role else None},
        )
        # §14.3: a system notification fires (high-stakes). Customer confirmation (§12.2).
        await publish_domain_event(DomainEvent(
            type=EventType.DISPUTE_OPENED, verification_id=verification_id,
            recipient_user_ids=(customer_id,),
            data={"vid": v.vid},
        ))
        return dispute

    async def agent_defend(self, dispute_id: str, agent_id: str, text: str) -> Dispute:
        """The affected agent's bounded-window defence, admin-mediated (§14.3)."""
        dispute = await self._repo.get_open_for_agent(dispute_id, agent_id)
        if dispute is None:
            raise ForbiddenException(message="No open dispute is awaiting your response.")
        if not (text or "").strip():
            raise ValidationException(message="A response is required.")
        hours = await self._config.get_int(ConfigKey.AGENT_DISPUTE_DEFENCE_HOURS)
        deadline = dispute.date_created + timedelta(hours=hours)
        if Utils.datetime_now() > deadline:
            raise ValidationException(message="The response window for this dispute has closed.")
        await self._repo.update(dispute.id, UpdateDisputeDto(agent_defence_text=text.strip()))
        await self._set_defended_at(dispute.id)
        self._audit.schedule(
            action=AuditActionType.DISPUTE_AGENT_DEFENDED,
            resource_type="dispute", resource_id=dispute.id, actor_id=agent_id,
            details={"verification_id": dispute.verification_id},
        )
        return await self._repo.get_model(dispute.id)

    async def resolve(self, dispute_id: str, dto: ResolveDisputeDto, admin_id: str) -> Dispute:
        """Admin resolves the dispute with one of the three §14.3 outcomes + a mandatory note."""
        dispute = await self._get(dispute_id)
        if dispute.status != DisputeStatus.OPEN.value:
            raise InvalidResourceStateException(
                resource="dispute", message="This dispute has already been resolved."
            )
        if not (dto.note or "").strip():
            raise ValidationException(message="A resolution note is required (delivered to the customer).")
        vid = dispute.verification_id
        verification = await self._verification_repo.get_model(vid)
        if verification is None or verification.status != VerificationStatus.DISPUTED.value:
            raise InvalidResourceStateException(
                resource="verification", message="The verification is not under dispute."
            )

        if dto.outcome == DisputeOutcome.REJECTED:
            await self._transition(vid, verification.status, VerificationStatus.COMPLETED)
            await self._commissions.unfreeze_for_verification(vid, admin_id)
        elif dto.outcome == DisputeOutcome.FULL_REFUND:
            await self._transition(vid, verification.status, VerificationStatus.REFUNDED)
            await self._payments.refund(vid, admin_id, reason="dispute_upheld_full_refund")
            await self._commissions.reverse_for_verification(vid, admin_id)
        else:  # PARTIAL_RECHECK
            roles = [r.value for r in (dto.scope_roles or [])]
            if not roles:
                raise ValidationException(message="Select at least one role for the free re-check.")
            # The re-checked release becomes v2.0.
            await self._verification_repo.update(
                vid, UpdateVerificationDto(
                    status=VerificationStatus.IN_PROGRESS.value,
                    pending_revision_kind=ReportRevisionKind.RECHECK.value,
                ),
            )
            for role_value in roles:
                await self._reviews.reopen_task(vid, AgentRole(role_value), admin_id)
            await self._commissions.unfreeze_for_verification(vid, admin_id)

        await self._repo.update(dispute.id, UpdateDisputeDto(
            status=DisputeStatus.RESOLVED.value, resolution_outcome=dto.outcome.value,
            resolution_note=dto.note.strip(), resolved_by=admin_id,
        ))
        await self._set_resolved_at(dispute.id)
        self._audit.schedule(
            action=AuditActionType.DISPUTE_RESOLVED,
            resource_type="dispute", resource_id=dispute.id, actor_id=admin_id,
            details={"verification_id": vid, "outcome": dto.outcome.value, "note": dto.note.strip()},
        )
        # The resolution note is delivered verbatim to the customer (§14.3).
        await publish_domain_event(DomainEvent(
            type=EventType.DISPUTE_RESOLVED, verification_id=vid,
            recipient_user_ids=(dispute.customer_id,),
            data={"outcome": dto.outcome.value, "note": dto.note.strip()},
        ))
        return await self._repo.get_model(dispute.id)

    async def list_for_verification(self, verification_id: str, customer_id: str) -> List[Dispute]:
        v = await self._verifications.get_owned(verification_id, customer_id)
        return await self._repo.list_for_verification(Utils.uuid_to_hex(v.id))

    async def page_open(self, page: int, page_size: int):
        """Admin queue of open disputes (paged), including any agent defence for review."""
        rows, total = await self._repo.page_open(offset=page * page_size, limit=page_size)
        dtos = [dispute_to_dto(d) for d in rows]
        return self._repo._db_utils.build_page(dtos, total, page, page_size)

    async def get(self, dispute_id: str) -> Dispute:
        return await self._get(dispute_id)

    # ── helpers ───────────────────────────────────────────────────

    async def _assert_within_window(self, verification_id: str) -> None:
        report = await self._reports.get_released(verification_id)
        if report is None:
            raise ValidationException(message="There is no released report to dispute.")
        if report.released_at is not None:
            window_days = await self._config.get_int(ConfigKey.DISPUTE_WINDOW_DAYS)
            if Utils.datetime_now() > report.released_at + timedelta(days=window_days):
                raise ValidationException(message="The dispute window for this report has closed.")

    async def _transition(self, vid: str, current: str, target: VerificationStatus) -> None:
        verification_state_machine.assert_can_transition(current, target.value, resource="Verification")
        await self._verification_repo.update(vid, UpdateVerificationDto(status=target.value))

    async def _notify_agent_defence(
        self, verification_id: str, agent_id: str, role: AgentRole, dispute
    ) -> None:
        """Best-effort admin-mediated breadcrumb into the agent thread — never surfaces the
        customer's identity, and never breaks the dispute-opening transaction."""
        try:
            from kink import di
            from main.app.domain.communication.service import CommunicationService

            comms = di[CommunicationService]
            await comms.auto_post_agent(
                verification_id, agent_id,
                f"A dispute has been raised regarding the {role.value.title()} task. Please provide "
                f"your account of the work so the admin can review it before resolving.",
            )
        except Exception:  # noqa: BLE001 — best-effort
            pass

    async def _get(self, dispute_id: str) -> Dispute:
        dispute = await self._repo.get_model(dispute_id)
        if dispute is None:
            raise ResourceNotFoundException(resource="dispute")
        return dispute

    async def _set_defended_at(self, dispute_id: str) -> None:
        dispute = await self._repo.get_model(dispute_id)
        dispute.agent_defence_at = Utils.datetime_now()

    async def _set_resolved_at(self, dispute_id: str) -> None:
        dispute = await self._repo.get_model(dispute_id)
        dispute.resolved_at = Utils.datetime_now()
