"""Payout service (PRD §15.1).

Agents withdraw cleared earnings to one of their saved, bank-resolved accounts; the
gateway's transfer fee is quoted up front and deducted from what reaches the bank. A request
draws down the available balance (netted against in-flight requests so nothing is
double-spent) and stamps a 2-business-day SLA. Finance approves, holds, adjusts, rejects,
and retries a failed transfer; approval queues the payout, and the money moves in the next
disbursement batch (`disbursement.py`). Every action is audited and notified (§12.2).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.sla import add_business_days
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.earnings.service import EarningsService
from main.app.domain.payout.bank_account.models import (
    AddBankAccountDto,
    AgentBankAccount,
    BankDto,
    ResolveBankAccountDto,
    ResolvedBankAccountDto,
)
from main.app.domain.payout.bank_account.service import BankAccountService
from main.app.domain.payout.disbursement import PayoutDisbursementService
from main.app.domain.payout.models import (
    ACTION_FROM_STATUSES,
    AdminPayoutDto,
    CreatePayoutDto,
    DisbursementQueueDto,
    Payout,
    PayoutAction,
    PayoutDecisionDto,
    PayoutDto,
    PayoutQuoteDto,
    PayoutStatus,
    QuotePayoutDto,
    RequestPayoutDto,
    admin_payout_to_dto,
    payout_to_dto,
    platform_of,
)
from main.app.domain.payout.repo import PayoutRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.appodus_utils import Utils
from main.appodus_utils.db.locks import advisory_xact_lock
from main.appodus_utils.db.models import Page
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.exception.exceptions import IntegrationException, IntegrationFatalException
from main.appodus_utils.integrations.factory import PaymentGatewayFactory
from main.appodus_utils.integrations.payment.gateway.models import GatewayTransferStatus

# One agent's withdrawals: the balance check and the reservation take turns on it.
_PAYOUT_LOCK = "payout"


def _note(dto: PayoutDecisionDto) -> dict:
    """The decision's note, when one was given; an absent note keeps the earlier one."""
    return {} if dto.note is None else {"note": dto.note}


def _require_positive_net(payout: Payout, adjustment_minor: int) -> None:
    """An adjustment may not leave nothing (or less) to pay once the transfer fee is taken."""
    if payout.amount_minor + adjustment_minor - (payout.fee_minor or 0) <= 0:
        raise ValidationException(message="The adjustment would leave nothing to pay after the transfer fee.")


def _not_allowed(action: PayoutAction) -> InvalidResourceStateException:
    message = {
        PayoutAction.CANCEL: "Only a pending request can be cancelled.",
        PayoutAction.RETRY: "Only a failed transfer can be retried.",
    }.get(action, "This payout can no longer be changed that way.")
    return InvalidResourceStateException(resource="payout", message=message)


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
        gateway_factory: PaymentGatewayFactory,
        disbursement_service: PayoutDisbursementService,
    ):
        self._payout_repo = payout_repo
        self._earnings = earnings_service
        self._banks = bank_account_service
        self._audit = audit_service
        self._config = config_service
        self._gateways = gateway_factory
        self._disbursement = disbursement_service

    # ── Agent ─────────────────────────────────────────────────────

    async def quote(self, agent_id: str, dto: QuotePayoutDto) -> PayoutQuoteDto:
        """The fee on a withdrawal of ``amount_minor`` to one of the agent's accounts, and
        what would reach the bank."""
        if dto.amount_minor <= 0:
            raise ValidationException(message="Withdrawal amount must be positive.")
        account = await self._payable_account(agent_id, dto.bank_account_id)
        fee = await self._fee(account, dto.amount_minor)
        return PayoutQuoteDto(amount_minor=dto.amount_minor, fee_minor=fee, net_minor=dto.amount_minor - fee)

    async def request(self, agent_id: str, dto: RequestPayoutDto) -> Payout:
        """Withdraw ``amount_minor`` to a saved account, net of the transfer fee (§15.1)."""
        if dto.amount_minor <= 0:
            raise ValidationException(message="Withdrawal amount must be positive.")
        account = await self._payable_account(agent_id, dto.bank_account_id)
        # Quoted before the lock: a gateway round trip must not hold the agent's other requests.
        fee = await self._fee(account, dto.amount_minor)
        if dto.amount_minor <= fee:
            raise ValidationException(message="The withdrawal must be more than the transfer fee.")
        # Balance check and reservation take turns per agent: a second request waits here,
        # then reads a balance that already nets out the first one's reservation.
        await advisory_xact_lock(f"{_PAYOUT_LOCK}:{agent_id}")
        available = await self._earnings.available_minor(agent_id)
        if dto.amount_minor > available:
            raise ValidationException(message="Withdrawal exceeds your available balance.")
        now = Utils.datetime_now()
        payout = await self._payout_repo.create_return_model(CreatePayoutDto(
            agent_id=agent_id, amount_minor=dto.amount_minor, fee_minor=fee,
            bank_name=account.bank_name, bank_code=account.bank_code, provider=account.provider,
            account_number=account.account_number, account_name=account.account_name,
        ))
        payout.requested_at = now
        payout.sla_due_at = await self._sla_due(now)
        self._audit.schedule(
            action=AuditActionType.PAYOUT_REQUESTED,
            resource_type="payout", resource_id=payout.id, actor_id=agent_id,
            details={"amount_minor": dto.amount_minor, "fee_minor": fee},
        )
        return payout

    async def cancel(self, agent_id: str, payout_id: str) -> Payout:
        """Agent withdraws a still-pending request (REQUESTED → CANCELLED); funds released."""
        payout = await self._get_owned(payout_id, agent_id)
        cancelled = await self._payout_repo.claim_transition(
            payout.id, ACTION_FROM_STATUSES[PayoutAction.CANCEL], PayoutStatus.CANCELLED,
        )
        if cancelled is None:
            raise _not_allowed(PayoutAction.CANCEL)
        self._audit.schedule(
            action=AuditActionType.PAYOUT_CANCELLED,
            resource_type="payout", resource_id=payout.id, actor_id=agent_id,
        )
        return cancelled

    async def list_banks(self) -> List[BankDto]:
        return await self._banks.list_banks()

    async def resolve_bank_account(self, dto: ResolveBankAccountDto) -> ResolvedBankAccountDto:
        return await self._banks.resolve(dto)

    async def list_bank_accounts(self, agent_id: str) -> List[AgentBankAccount]:
        return await self._banks.list_for_agent(agent_id)

    async def add_bank_account(self, agent_id: str, dto: AddBankAccountDto) -> AgentBankAccount:
        return await self._banks.add(agent_id, dto)

    async def remove_bank_account(self, agent_id: str, account_id: str) -> None:
        await self._banks.remove(agent_id, account_id)

    async def page_for_agent(self, agent_id: str, page: int, page_size: int) -> Page[PayoutDto]:
        rows, total = await self._payout_repo.page_for_agent(agent_id, page, page_size)
        return self._payout_repo._db_utils.build_page([payout_to_dto(p) for p in rows], total, page, page_size)

    # ── Finance (APPROVE_PAYOUT) ──────────────────────────────────

    async def approve(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Approve for the next disbursement batch — REQUESTED/HELD → APPROVED (§12.2)."""
        payout = await self._get(payout_id)
        self._require_payable_account(payout)
        decided = await self._decide(payout, PayoutAction.APPROVE, PayoutStatus.APPROVED, admin_id, dto,
                                     AuditActionType.PAYOUT_APPROVED)
        await publish_domain_event(DomainEvent(
            type=EventType.PAYOUT_APPROVED, recipient_user_ids=(payout.agent_id,),
        ))
        return decided

    async def hold(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Hold pending review — REQUESTED/APPROVED → HELD; fires PAYOUT_HELD with the reason."""
        payout = await self._get(payout_id)
        decided = await self._decide(payout, PayoutAction.HOLD, PayoutStatus.HELD, admin_id, dto,
                                     AuditActionType.PAYOUT_HELD)
        await publish_domain_event(DomainEvent(
            type=EventType.PAYOUT_HELD, recipient_user_ids=(payout.agent_id,),
            data={"reason": dto.note or "under review"},
        ))
        return decided

    async def reject(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Decline — anything not yet sent → REJECTED; funds released back to available."""
        payout = await self._get(payout_id)
        decided = await self._decide(payout, PayoutAction.REJECT, PayoutStatus.REJECTED, admin_id, dto,
                                     AuditActionType.PAYOUT_REJECTED)
        await publish_domain_event(DomainEvent(
            type=EventType.PAYOUT_REJECTED, recipient_user_ids=(payout.agent_id,),
            data={"reason": dto.note or "declined by finance"},
        ))
        return decided

    async def adjust(self, payout_id: str, admin_id: str, dto: PayoutDecisionDto) -> Payout:
        """Record a finance correction (an adjustment + note) without deciding the request."""
        payout = await self._get(payout_id)
        adjustment = dto.adjustment_minor or 0
        _require_positive_net(payout, adjustment)
        # Written only while nothing has been sent: an adjustment landing after a transfer
        # left would change a disbursement that is already on its way.
        adjusted = await self._payout_repo.claim_transition(
            payout.id, ACTION_FROM_STATUSES[PayoutAction.ADJUST], adjustment_minor=adjustment, **_note(dto),
        )
        if adjusted is None:
            raise _not_allowed(PayoutAction.ADJUST)
        self._audit.schedule(
            action=AuditActionType.PAYOUT_ADJUSTED,
            resource_type="payout", resource_id=payout.id, actor_id=admin_id,
            details={"adjustment_minor": adjustment, "note": dto.note},
        )
        return adjusted

    async def retry(self, payout_id: str, admin_id: str) -> Payout:
        """Send a failed transfer again — FAILED → APPROVED, into the next batch. The new
        attempt gets its own reference, so it can never be mistaken for the one that failed.

        A retry is the one move that could pay an agent twice, so it first asks the gateway
        about the failed attempt: one that went through after all is settled as paid instead,
        and one the gateway cannot yet vouch for is refused until it can."""
        payout = await self._get(payout_id)
        if payout.status != PayoutStatus.FAILED.value:
            raise _not_allowed(PayoutAction.RETRY)
        self._require_payable_account(payout)
        if payout.transfer_reference:
            await self._confirm_last_attempt_failed(payout)
        retried = await self._payout_repo.claim_transition(
            payout.id, ACTION_FROM_STATUSES[PayoutAction.RETRY], PayoutStatus.APPROVED,
            failure_reason=None, decided_by=admin_id, decided_at=Utils.datetime_now(),
        )
        if retried is None:
            raise _not_allowed(PayoutAction.RETRY)
        self._audit.schedule(
            action=AuditActionType.PAYOUT_RETRIED, resource_type="payout", resource_id=payout.id,
            actor_id=admin_id, from_state=PayoutStatus.FAILED.value, to_state=PayoutStatus.APPROVED.value,
            details={"attempts": payout.transfer_attempts},
        )
        return retried

    async def page_all(self, page: int, page_size: int, status: str | None = None) -> Page[AdminPayoutDto]:
        rows, total = await self._payout_repo.page_all(page, page_size, status)
        return self._payout_repo._db_utils.build_page([admin_payout_to_dto(p) for p in rows], total, page, page_size)

    async def disbursement_queue(self) -> DisbursementQueueDto:
        """Approved payouts waiting for the next batch, and what they will draw."""
        count, total = await self._payout_repo.approved_totals()
        in_flight = await self._payout_repo.count_in_status(PayoutStatus.PROCESSING)
        return DisbursementQueueDto(count=count, total_minor=total, in_flight=in_flight)

    # ── helpers ───────────────────────────────────────────────────

    async def _payable_account(self, agent_id: str, account_id: str) -> AgentBankAccount:
        account = await self._banks.get_owned(agent_id, account_id)
        if not account.bank_code:
            raise ValidationException(
                message="This account was saved before accounts were checked with the bank. "
                        "Remove it and add it again."
            )
        return account

    async def _fee(self, account: AgentBankAccount, amount_minor: int) -> int:
        try:
            gateway = self._gateways.transfers(platform_of(account.provider))
        except IntegrationFatalException:
            # Saved under the stub, but live now: no live gateway knows its bank code.
            raise ValidationException(
                message="This account can't be paid yet. Remove it and add it again."
            ) from None
        return await gateway.quote_fee(amount_minor, TransactionCurrency.NGN)

    @staticmethod
    def _require_payable_account(payout: Payout) -> None:
        if not payout.bank_code:
            raise ValidationException(
                message="This payout was requested before accounts were checked with the bank, so it "
                        "can't be sent. Reject it and ask the agent to request again."
            )

    async def _confirm_last_attempt_failed(self, payout: Payout) -> None:
        reference = payout.transfer_reference
        try:
            last = await self._gateways.transfers(platform_of(payout.provider)).get_transfer(reference)
        except IntegrationFatalException:
            raise ValidationException(message="This account can't be paid. Reject the payout instead.") from None
        except IntegrationException:
            raise InvalidResourceStateException(
                resource="payout",
                message="Couldn't confirm the last transfer with the payment gateway. Try again shortly.",
            ) from None
        if last is None or last.status == GatewayTransferStatus.FAILED:
            return
        if last.status == GatewayTransferStatus.SUCCEEDED:
            # Recorded in its own transaction, so it stands although this retry is refused.
            await self._disbursement.settle_from_gateway(reference)
            raise InvalidResourceStateException(
                resource="payout", message="That transfer went through after all; the payout is now marked paid.",
            )
        raise InvalidResourceStateException(
            resource="payout", message="The last transfer is still with the bank. Retry once it has failed.",
        )

    async def _decide(
        self, payout: Payout, action: PayoutAction, to_status: PayoutStatus, admin_id: str,
        dto: PayoutDecisionDto, audit_action: AuditActionType,
    ) -> Payout:
        """Claim the decision: exactly one of two concurrent finance decisions lands, and
        the other is refused before it can notify."""
        if dto.adjustment_minor is not None:
            _require_positive_net(payout, dto.adjustment_minor)
        adjustment = {} if dto.adjustment_minor is None else {"adjustment_minor": dto.adjustment_minor}
        decided = await self._payout_repo.claim_transition(
            payout.id, ACTION_FROM_STATUSES[action], to_status,
            decided_by=admin_id, decided_at=Utils.datetime_now(), **_note(dto), **adjustment,
        )
        if decided is None:
            raise _not_allowed(action)
        self._audit.schedule(
            action=audit_action, resource_type="payout", resource_id=payout.id, actor_id=admin_id,
            from_state=payout.status, to_state=to_status.value,
            details={"note": dto.note} if dto.note else None,
        )
        return decided

    async def _get_owned(self, payout_id: str, agent_id: str) -> Payout:
        payout = await self._payout_repo.get_model(payout_id)
        if payout is None or payout.deleted or payout.agent_id != agent_id:
            raise ResourceNotFoundException(resource="payout")
        return payout

    async def _get(self, payout_id: str) -> Payout:
        payout = await self._payout_repo.get_model(payout_id)
        if payout is None or payout.deleted:
            raise ResourceNotFoundException(resource="payout")
        return payout

    async def _sla_due(self, now: datetime) -> datetime:
        sla_days = await self._config.get_int(ConfigKey.PAYOUT_SLA_BUSINESS_DAYS)
        due = add_business_days(now, sla_days)
        return datetime(due.year, due.month, due.day, tzinfo=timezone.utc)
