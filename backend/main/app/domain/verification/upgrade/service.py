"""Tier-upgrade service (PRD §14.2).

A customer upgrades a verification to a richer tier for the price delta only. On payment the
verification's tier is raised, the added scope's tasks are instantiated (existing approved work
is preserved), the SLA is extended, and the verification returns to work. The next release bumps
the report to v3.0 (revision_kind TIER_UPGRADE). Idempotent on resubmit — a second request for
the same target tier returns the pending one rather than charging twice.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.realtime import VerificationEventType
from main.app.core.sla import sla_due_date
from main.app.core.state.status import ReportRevisionKind, VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.models import PaymentPurpose
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.models import UpdateVerificationDto
from main.app.domain.verification.pricing import is_upgrade, upgrade_delta_kobo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.service import VerificationTaskService
from main.app.domain.verification.upgrade.models import (
    CreateUpgradeDto,
    RequestUpgradeDto,
    UpdateUpgradeDto,
    UpgradeRequest,
    UpgradeStatus,
)
from main.app.domain.verification.upgrade.repo import UpgradeRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_UPGRADEABLE = {VerificationStatus.COMPLETED.value, VerificationStatus.IN_PROGRESS.value}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class UpgradeService:
    def __init__(
        self,
        upgrade_repo: UpgradeRepo,
        verification_service: VerificationService,
        verification_repo: VerificationRepo,
        task_service: VerificationTaskService,
        payment_service: PaymentService,
        audit_service: AuditLogService,
    ):
        self._repo = upgrade_repo
        self._verifications = verification_service
        self._verification_repo = verification_repo
        self._tasks = task_service
        self._payments = payment_service
        self._audit = audit_service

    async def request(
        self, verification_id: str, customer_id: str, dto: RequestUpgradeDto
    ) -> UpgradeRequest:
        """Request a tier upgrade (§14.2). Idempotent on resubmit for the same target tier."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        if v.status not in _UPGRADEABLE:
            raise InvalidResourceStateException(
                resource="verification",
                message="A tier upgrade is only available on a completed or in-progress verification.",
            )
        current = VerificationTier(v.tier)
        target = dto.to_tier
        if not is_upgrade(current, target):
            raise ValidationException(message="The selected tier is not an upgrade.")

        key = f"{Utils.uuid_to_hex(v.id)}:{target.value}"
        existing = await self._repo.get_by_key(key)
        if existing is not None and existing.status == UpgradeStatus.PENDING.value:
            return existing  # idempotent — reuse the pending request + its charge

        delta = upgrade_delta_kobo(current, target)
        payment = await self._payments.initiate_secondary(
            verification_id=Utils.uuid_to_hex(v.id), customer_id=customer_id,
            amount_minor=delta, purpose=PaymentPurpose.UPGRADE,
        )
        upgrade = await self._repo.create_return_model(CreateUpgradeDto(
            verification_id=Utils.uuid_to_hex(v.id), customer_id=customer_id,
            from_tier=current, to_tier=target, delta_minor=delta, idempotency_key=key,
        ))
        await self._repo.update(upgrade.id, UpdateUpgradeDto(payment_id=payment.id))
        self._audit.schedule(
            action=AuditActionType.TIER_UPGRADE_REQUESTED,
            resource_type="upgrade", resource_id=upgrade.id, actor_id=customer_id,
            details={"verification_id": verification_id, "from": current.value,
                     "to": target.value, "delta_minor": delta, "payment_id": payment.id},
        )
        return await self._repo.get_model(upgrade.id)

    async def on_payment_confirmed(self, payment_id: str) -> None:
        """Apply the upgrade once the delta is paid (webhook, §14.2). Idempotent."""
        upgrade = await self._repo.get_by_payment(payment_id)
        if upgrade is None or upgrade.status != UpgradeStatus.PENDING.value:
            return
        verification = await self._verification_repo.get_model(upgrade.verification_id)
        if verification is None:
            return

        was_completed = verification.status == VerificationStatus.COMPLETED.value
        new_status = VerificationStatus.IN_PROGRESS.value if was_completed else verification.status
        await self._verification_repo.update(upgrade.verification_id, UpdateVerificationDto(
            tier=upgrade.to_tier,
            status=new_status,
            pending_revision_kind=ReportRevisionKind.TIER_UPGRADE.value,
        ))
        # Extend the SLA for the richer tier (date field → set on the model).
        row = await self._verification_repo.get_model(upgrade.verification_id)
        if row is not None:
            row.sla_due_date = sla_due_date(Utils.datetime_now(), VerificationTier(upgrade.to_tier))

        # Add the new scope's tasks; existing APPROVED tasks are preserved (instantiate skips
        # roles already present). Broadcast to the pool when auto-assignment is enabled (§6.2).
        await self._tasks.prepare_for_paid(upgrade.verification_id)

        await self._repo.update(upgrade.id, UpdateUpgradeDto(status=UpgradeStatus.PAID.value))
        self._audit.schedule(
            action=AuditActionType.TIER_UPGRADE_APPLIED,
            resource_type="upgrade", resource_id=upgrade.id, actor_id=upgrade.customer_id,
            from_state=upgrade.from_tier, to_state=upgrade.to_tier,
            details={"verification_id": upgrade.verification_id},
        )
        if was_completed:
            await publish_domain_event(DomainEvent(
                type=EventType.STATUS_CHANGED, verification_id=upgrade.verification_id,
                recipient_user_ids=(upgrade.customer_id,),
                sse_event=VerificationEventType.STATUS_CHANGED.value,
                data={"status": VerificationStatus.IN_PROGRESS.value},
            ))

    async def list_for_verification(self, verification_id: str, customer_id: str) -> List[UpgradeRequest]:
        v = await self._verifications.get_owned(verification_id, customer_id)
        return await self._repo.list_for_verification(Utils.uuid_to_hex(v.id))

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, upgrade_id: str) -> UpgradeRequest:
        upgrade = await self._repo.get_model(upgrade_id)
        if upgrade is None:
            raise ResourceNotFoundException(resource="upgrade")
        return upgrade
