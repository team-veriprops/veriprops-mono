"""Payout service (PRD §15.1).

Agents withdraw cleared earnings; Finance approves / holds / adjusts / rejects. A request
draws down the available balance (netted against in-flight requests so nothing is
double-spent) and stamps a 2-business-day SLA. Disbursement is stub-first (§PAYMENT_STUB_MODE
posture): approval marks the payout PAID and fires PAYOUT_APPROVED; a real transfer gateway
drops in behind this later. Every action is audited and notified (§12.2).
"""
from __future__ import annotations

from datetime import datetime, timezone

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.sla import add_business_days
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.earnings.service import EarningsService
from main.app.domain.payout.bank_account.service import BankAccountService
from main.app.domain.payout.models import (
    CreatePayoutDto,
    LOCKING_STATUSES,
    Payout,
    PayoutDecisionDto,
    PayoutDto,
    PayoutStatus,
    RequestPayoutDto,
    UpdatePayoutDto,
    payout_to_dto,
)
from main.app.domain.payout.repo import PayoutRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PayoutService:
    def __init__(
        self,
        payout_repo: PayoutRepo,
        earnings_service: EarningsService,
        bank_account_service: BankAccountService,
        audit_service: AuditLogService,
        config_service: ConfigService,
    ):
        self._payout_repo = payout_repo
        self._earnings = earnings_service
        self._banks = bank_account_service
        self._audit = audit_service
        self._config = config_service

    # ── Agent ─────────────────────────────────────────────────────

    async def request(self, agent_id: str, dto: RequestPayoutDto) -> Payout:
        """Withdraw ``amount_minor`` to a stored or one-time beneficiary (§15.1)."""
        if dto.amount_minor <= 0:
            raise ValidationException(message="Withdrawal amount must be positive.")
        available = await self._earnings.available_minor(agent_id)
        if dto.amount_minor > available:
            raise ValidationException(
                message="Withdrawal exceeds your available balance."
            )
        bank_name, account_number, account_name = await self._resolve_beneficiary(agent_id, dto)
        now = Utils.datetime_now()
        payout = await self._payout_repo.create_return_model(CreatePayoutDto(
            agent_id=agent_id, amount_minor=dto.amount_minor,
            bank_name=bank_name, account_number=account_number, account_name=account_name,
        ))
        payout.requested_at = now
        payout.sla_due_at = await self._sla_due(now)
        self._audit.schedule(
            action=AuditActionType.PAYOUT_REQUESTED,
            resource_type="payout", resource_id=payout.id, actor_id=agent_id,
            details={"amount_minor": dto.amount_minor},
        )
        return payout

    async def cancel(self, agent_id: str, payout_id: str) -> Payout:
        """Agent withdraws a still-pending request (REQUESTED → CANCELLED); funds released."""
        payout = await self._get_owned(payout_id, agent_id)
        if payout.status != PayoutStatus.REQUESTED.value:
            raise InvalidResourceStateException(
                resource="payout", message="Only a pending request can be cancelled."
            )
        await self._payout_repo.update(payout.id, UpdatePayoutDto(status=PayoutStatus.CANCELLED.value))
        self._audit.schedule(
            action=AuditActionType.PAYOUT_CANCELLED,
            resource_type="payout", resource_id=payout.id, actor_id=agent_id,
        )
        return await self._payout_repo.get_model(payout.id)

    async def list_bank_accounts(self, agent_id: str):
        return await self._banks.list_for_agent(agent_id)

    async def add_bank_account(self, agent_id: str, dto):
        return await self._banks.add(agent_id, dto)

    async def remove_bank_account(self, agent_id: str, account_id: str) -> None:
        await self._banks.remove(agent_id, account_id)

    async def page_for_agent(self, agent_id: str, page: int, page_size: int) -> Page[PayoutDto]:
        rows, total = await self._payout_repo.page_for_agent(agent_id, page, page_size)
        return self._payout_repo._db_utils.build_page([payout_to_dto(p) for p in rows], total, page, page_size)

    # ── Finance (APPROVE_PAYOUT) ──────────────────────────────────

    async def approve(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Approve + disburse (stub) — REQUESTED/HELD → PAID; fires PAYOUT_APPROVED (§12.2)."""
        # TODO(gap): stub disbursement — approval marks PAID directly; wire a real transfer
        # gateway behind the payment facade — PRD "Known Gaps & Roadmap".
        payout = await self._get_decidable(payout_id)
        await self._decide(payout, PayoutStatus.PAID, admin_id, dto,
                            AuditActionType.PAYOUT_APPROVED)
        await publish_domain_event(DomainEvent(
            type=EventType.PAYOUT_APPROVED, recipient_user_ids=(payout.agent_id,),
        ))
        return await self._payout_repo.get_model(payout.id)

    async def hold(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Hold pending review — REQUESTED → HELD; fires PAYOUT_HELD with the reason (§12.2)."""
        payout = await self._get_decidable(payout_id)
        await self._decide(payout, PayoutStatus.HELD, admin_id, dto, AuditActionType.PAYOUT_HELD)
        await publish_domain_event(DomainEvent(
            type=EventType.PAYOUT_HELD, recipient_user_ids=(payout.agent_id,),
            data={"reason": dto.note or "under review"},
        ))
        return await self._payout_repo.get_model(payout.id)

    async def reject(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Decline — REQUESTED/HELD → REJECTED; funds released back to available."""
        payout = await self._get_decidable(payout_id)
        await self._decide(payout, PayoutStatus.REJECTED, admin_id, dto,
                           AuditActionType.PAYOUT_REJECTED)
        return await self._payout_repo.get_model(payout.id)

    async def adjust(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Record a finance correction (an adjustment + note) without deciding the request."""
        payout = await self._get_decidable(payout_id)
        await self._payout_repo.update(payout.id, UpdatePayoutDto(
            adjustment_minor=dto.adjustment_minor or 0, note=dto.note,
        ))
        self._audit.schedule(
            action=AuditActionType.PAYOUT_ADJUSTED,
            resource_type="payout", resource_id=payout.id, actor_id=admin_id,
            details={"adjustment_minor": dto.adjustment_minor or 0, "note": dto.note},
        )
        return await self._payout_repo.get_model(payout.id)

    async def page_all(self, page: int, page_size: int, status: str | None = None) -> Page[PayoutDto]:
        rows, total = await self._payout_repo.page_all(page, page_size, status)
        return self._payout_repo._db_utils.build_page([payout_to_dto(p) for p in rows], total, page, page_size)

    # ── helpers ───────────────────────────────────────────────────

    async def _resolve_beneficiary(self, agent_id: str, dto: RequestPayoutDto):
        if dto.bank_account_id:
            # Key by the wire id form (.hex) so a stored-account id from the client matches.
            accounts = {Utils.uuid_to_hex(a.id): a for a in await self._banks.list_for_agent(agent_id)}
            account = accounts.get(dto.bank_account_id)
            if account is None:
                raise ResourceNotFoundException(resource="bank_account")
            return account.bank_name, account.account_number, account.account_name
        if not (dto.bank_name and dto.account_number and dto.account_name):
            raise ValidationException(
                message="Provide a saved bank account or full one-time bank details."
            )
        return dto.bank_name, dto.account_number, dto.account_name

    async def _decide(
        self, payout: Payout, to_status: PayoutStatus, admin_id: str,
        dto: PayoutDecisionDto, action: AuditActionType,
    ) -> None:
        await self._payout_repo.update(payout.id, UpdatePayoutDto(
            status=to_status.value, decided_by=admin_id, note=dto.note,
            adjustment_minor=dto.adjustment_minor if dto.adjustment_minor is not None else None,
        ))
        row = await self._payout_repo.get_model(payout.id)
        row.decided_at = Utils.datetime_now()
        self._audit.schedule(
            action=action, resource_type="payout", resource_id=payout.id, actor_id=admin_id,
            from_state=payout.status, to_state=to_status.value,
            details={"note": dto.note} if dto.note else None,
        )

    async def _get_owned(self, payout_id: str, agent_id: str) -> Payout:
        payout = await self._payout_repo.get_model(payout_id)
        if payout is None or payout.deleted or payout.agent_id != agent_id:
            raise ResourceNotFoundException(resource="payout")
        return payout

    async def _get_decidable(self, payout_id: str) -> Payout:
        payout = await self._payout_repo.get_model(payout_id)
        if payout is None or payout.deleted:
            raise ResourceNotFoundException(resource="payout")
        if payout.status not in LOCKING_STATUSES:
            raise InvalidResourceStateException(
                resource="payout", message="This payout has already been finalised."
            )
        return payout

    async def _sla_due(self, now: datetime) -> datetime:
        sla_days = await self._config.get_int(ConfigKey.PAYOUT_SLA_BUSINESS_DAYS)
        due = add_business_days(now, sla_days)
        return datetime(due.year, due.month, due.day, tzinfo=timezone.utc)
