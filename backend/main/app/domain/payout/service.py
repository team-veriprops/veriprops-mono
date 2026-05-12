"""Payout service — S48."""
from __future__ import annotations

from decimal import Decimal
from typing import List, TYPE_CHECKING

from kink import di, inject

from main.app.domain.payout.models import (
    AdjustPayoutDto,
    BankAccountDto,
    CreateBankAccountDto,
    CreatePayoutAdjustmentDto,
    CreatePayoutDto,
    HoldPayoutDto,
    PayoutDto,
    PayoutStatus,
    SearchPayoutDto,
    UpdatePayoutDto,
    WithdrawalRequestDto,
)
from main.app.domain.payout.repo import BankAccountRepo, PayoutAdjustmentRepo, PayoutRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PayoutService:
    def __init__(
        self,
        payout_repo: PayoutRepo,
        bank_repo: BankAccountRepo,
        adjustment_repo: PayoutAdjustmentRepo,
    ):
        self._payout_repo = payout_repo
        self._bank_repo = bank_repo
        self._adjustment_repo = adjustment_repo

    # ── Bank accounts ─────────────────────────────────────────────

    async def list_bank_accounts(self, agent_id: str) -> List[BankAccountDto]:
        rows = await self._bank_repo.list_for_agent(agent_id)
        return [self._bank_to_dto(r) for r in rows]

    async def add_bank_account(self, agent_id: str, dto: CreateBankAccountDto) -> BankAccountDto:
        dto.agent_id = agent_id
        row = await self._bank_repo.create(dto)
        return self._bank_to_dto(row)

    # ── Payouts ───────────────────────────────────────────────────

    async def submit_withdrawal(self, agent_id: str, dto: WithdrawalRequestDto) -> PayoutDto:
        from main.app.domain.commission.service import CommissionService
        commission_svc: CommissionService = di[CommissionService]
        available = await commission_svc.available_balance(agent_id)
        if Decimal(str(dto.amount)) > available:
            raise ValidationException(message=f"Amount {dto.amount} exceeds available balance {available}")

        bank = await self._bank_repo.get_model(dto.bank_account_id)
        if bank is None or str(bank.agent_id) != agent_id:
            raise ResourceNotFoundException(resource="BankAccount")

        now_str = str(Utils.datetime_now())
        row = await self._payout_repo.create(CreatePayoutDto(
            agent_id=agent_id,
            amount=dto.amount,
            bank_account_id=dto.bank_account_id,
            status=PayoutStatus.PENDING.value,
            requested_at=now_str,
        ))
        return self._payout_to_dto(row)

    async def list_payouts(self, agent_id: str) -> List[PayoutDto]:
        rows = await self._payout_repo.list_for_agent(agent_id)
        return [self._payout_to_dto(r) for r in rows]

    async def list_all_payouts(self) -> List[PayoutDto]:
        rows = await self._payout_repo.get_all(SearchPayoutDto())
        return [self._payout_to_dto(r) for r in rows]

    async def approve(self, payout_id: str, admin_id: str) -> PayoutDto:
        row = await self._get_or_raise(payout_id)
        await self._payout_repo.update(payout_id, UpdatePayoutDto(
            status=PayoutStatus.APPROVED.value,
            approved_at=str(Utils.datetime_now()),
        ))
        await self._notify_safe(str(row.agent_id), "approved", "")
        return self._payout_to_dto(await self._payout_repo.get_model(payout_id))

    async def hold(self, payout_id: str, dto: HoldPayoutDto, admin_id: str) -> PayoutDto:
        await self._get_or_raise(payout_id)
        await self._payout_repo.update(payout_id, UpdatePayoutDto(
            status=PayoutStatus.ON_HOLD.value,
            hold_reason=dto.reason,
        ))
        row = await self._payout_repo.get_model(payout_id)
        await self._notify_safe(str(row.agent_id), "held", dto.reason)
        return self._payout_to_dto(row)

    async def adjust(self, payout_id: str, dto: AdjustPayoutDto, admin_id: str) -> PayoutDto:
        row = await self._get_or_raise(payout_id)
        await self._adjustment_repo.create(CreatePayoutAdjustmentDto(
            payout_id=payout_id,
            adjusted_by=admin_id,
            original_amount=float(row.amount),
            new_amount=dto.new_amount,
            reason=dto.reason,
        ))
        await self._payout_repo.update(payout_id, UpdatePayoutDto(amount=dto.new_amount))
        return self._payout_to_dto(await self._payout_repo.get_model(payout_id))

    async def mark_paid(self, payout_id: str) -> PayoutDto:
        await self._get_or_raise(payout_id)
        await self._payout_repo.update(payout_id, UpdatePayoutDto(
            status=PayoutStatus.PAID.value,
            paid_at=str(Utils.datetime_now()),
        ))
        # Mark corresponding earnings as PAID
        try:
            row = await self._payout_repo.get_model(payout_id)
            from main.app.domain.commission.repo import EarningRepo
            from main.app.domain.commission.models import EarningStatus, UpdateEarningDto, SearchEarningDto
            earning_repo: EarningRepo = di[EarningRepo]
            earnings = await earning_repo.list_for_agent(str(row.agent_id))
            for e in earnings:
                if e.status == EarningStatus.PENDING.value:
                    await earning_repo.update(str(e.id), UpdateEarningDto(status=EarningStatus.PAID.value))
        except Exception as exc:
            logger.warning(f"Failed to mark earnings paid for payout {payout_id}: {exc}")
        return self._payout_to_dto(await self._payout_repo.get_model(payout_id))

    # ── Helpers ───────────────────────────────────────────────────

    async def _get_or_raise(self, payout_id: str):
        row = await self._payout_repo.get_model(payout_id)
        if row is None:
            raise ResourceNotFoundException(resource="Payout")
        return row

    async def _notify_safe(self, agent_id: str, action: str, reason: str) -> None:
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            notif_svc: NotificationService = di[NotificationService]
            event = NotificationEvent.PAYOUT_APPROVED if action == "approved" else NotificationEvent.PAYOUT_HELD
            await notif_svc.emit(event, recipient_id=agent_id, context={"reason": reason})
        except Exception as exc:
            logger.warning(f"Notification emit failed (payout {action}): {exc}")

    def _payout_to_dto(self, row) -> PayoutDto:
        return PayoutDto(
            id=str(row.id),
            agent_id=str(row.agent_id),
            amount=float(row.amount),
            bank_account_id=str(row.bank_account_id),
            status=PayoutStatus(row.status),
            requested_at=str(row.requested_at),
            approved_at=str(row.approved_at) if row.approved_at else None,
            paid_at=str(row.paid_at) if row.paid_at else None,
            hold_reason=row.hold_reason,
            date_created=str(row.date_created),
        )

    def _bank_to_dto(self, row) -> BankAccountDto:
        return BankAccountDto(
            id=str(row.id),
            agent_id=str(row.agent_id),
            bank_name=row.bank_name,
            account_number=row.account_number,
            account_holder_name=row.account_holder_name,
            is_default=row.is_default,
            date_created=str(row.date_created),
        )
