"""Commission service (PRD §15.2 / §6a.2 — early per D13).

Freeze / unfreeze / reverse operations drive the chargeback sub-process (§6a):
- **freeze** on chargeback flag — CLEARING/AVAILABLE commissions pause immediately;
- **unfreeze** on chargeback won — restore the pre-freeze status;
- **reverse** on chargeback lost — claw the money back (→ REVERSED).

Accrual (creating CLEARING commissions on task approval) lands in S12; the earnings
dashboard and payouts build on this in S19.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.models import (
    Commission,
    CommissionStatus,
    CreateCommissionDto,
    UpdateCommissionDto,
)
from main.app.domain.commission.repo import CommissionRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# Commissions still exposed to a chargeback clawback (not yet paid out).
_FREEZABLE = [CommissionStatus.CLEARING.value, CommissionStatus.AVAILABLE.value]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommissionService:
    def __init__(self, commission_repo: CommissionRepo, audit_service: AuditLogService):
        self._repo = commission_repo
        self._audit = audit_service

    async def accrue(self, dto: CreateCommissionDto) -> Commission:
        """Record a commission in CLEARING (called on task approval in S12)."""
        commission = await self._repo.create_return_model(dto)
        self._audit.schedule(
            action=AuditActionType.COMMISSION_ACCRUED,
            resource_type="commission",
            resource_id=commission.id,
            actor_id=None,
            details={"verification_id": dto.verification_id, "agent_id": dto.agent_id,
                     "amount_minor": dto.amount_minor},
        )
        return commission

    async def freeze_for_verification(self, verification_id: str, actor_id: str) -> int:
        """Freeze every freezable commission on a verification (§6a.2). Idempotent:
        already-frozen/reversed commissions are skipped. Returns the count frozen."""
        commissions = await self._repo.list_for_verification_in_status(verification_id, _FREEZABLE)
        for c in commissions:
            await self._repo.update(c.id, UpdateCommissionDto(
                status=CommissionStatus.FROZEN.value,
                frozen_from_status=c.status,
            ))
            self._audit.schedule(
                action=AuditActionType.COMMISSION_FROZEN,
                resource_type="commission",
                resource_id=c.id,
                actor_id=actor_id,
                from_state=c.status,
                to_state=CommissionStatus.FROZEN.value,
            )
        return len(commissions)

    async def unfreeze_for_verification(self, verification_id: str, actor_id: str) -> int:
        """Restore frozen commissions to their pre-freeze status (chargeback won)."""
        frozen = await self._repo.list_for_verification_in_status(
            verification_id, [CommissionStatus.FROZEN.value]
        )
        for c in frozen:
            restore = c.frozen_from_status or CommissionStatus.CLEARING.value
            await self._repo.update(c.id, UpdateCommissionDto(status=restore))
            self._audit.schedule(
                action=AuditActionType.COMMISSION_UNFROZEN,
                resource_type="commission",
                resource_id=c.id,
                actor_id=actor_id,
                from_state=CommissionStatus.FROZEN.value,
                to_state=restore,
            )
        return len(frozen)

    async def reverse_for_verification(self, verification_id: str, actor_id: str) -> int:
        """Claw back frozen/clearing/available commissions (chargeback lost)."""
        exposed = await self._repo.list_for_verification_in_status(
            verification_id,
            [CommissionStatus.FROZEN.value, *_FREEZABLE],
        )
        for c in exposed:
            await self._repo.update(c.id, UpdateCommissionDto(status=CommissionStatus.REVERSED.value))
            self._audit.schedule(
                action=AuditActionType.COMMISSION_REVERSED,
                resource_type="commission",
                resource_id=c.id,
                actor_id=actor_id,
                from_state=c.status,
                to_state=CommissionStatus.REVERSED.value,
            )
        return len(exposed)

    async def list_for_verification(self, verification_id: str) -> List[Commission]:
        return await self._repo.list_for_verification(verification_id)

    async def get_live_for_task(self, verification_id: str, task_id: str):
        """A non-reversed commission already accrued for this task, or None (double-accrual guard)."""
        return await self._repo.get_live_for_task(verification_id, task_id)
