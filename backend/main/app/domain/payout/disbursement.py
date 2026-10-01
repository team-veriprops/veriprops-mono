"""Payout disbursement — approved payouts leave as bank transfers, in batches (PRD §15.1).

A batch runs from the daily sweep (`app/jobs/tasks/payout_sweeps.py`) or from finance's
"disburse" button, and both run the same thing: settle transfers still in flight, then send
approved payouts, oldest decision first, up to a limit.

The property all of this protects is that **an agent is never paid twice**:

* A payout is claimed APPROVED → PROCESSING under a fresh transfer reference, and the claim
  commits in its own transaction *before* the gateway is called. However the process dies
  after the money moved, the payout is left PROCESSING, never back in the queue.
* Each attempt has its own reference, and both gateways refuse a second transfer under a
  reference they have seen.
* Only the gateway's own "no" — a decline, then no transfer found under our reference —
  fails a payout. An unreachable gateway or a lost answer leaves it PROCESSING for a later
  run to settle by asking the gateway for our reference.
* A webhook only says "go and look": a payout settles from what the gateway reports when
  asked, and only for the attempt it names.

A failed transfer keeps its funds reserved; finance retries it (a new attempt) or rejects it.
Each step writes in an `INDEPENDENT` transaction, so one payout's outcome never waits on, or
rolls back with, another's.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Awaitable, Optional, Union

from kink import di, inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payout.models import (
    DisbursementOutcomeDto,
    Payout,
    PayoutStatus,
    net_minor,
    platform_of,
)
from main.app.domain.payout.repo import PayoutRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.factory import PaymentGatewayFactory
from main.appodus_utils.integrations.payment.gateway.http import GatewayDeclined
from main.appodus_utils.integrations.payment.gateway.interface import ITransferGateway
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayTransfer,
    GatewayTransferStatus,
    TransferRequest,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di["logger"]

# Payouts one run sends. A serverless request has a time limit, and the button reports what
# is left, so finance presses again rather than one press timing out part-way.
DISBURSEMENT_BATCH_SIZE = 25
# A transfer handed over this long ago with no outcome is looked up rather than left to its
# webhook; one the gateway still has no record of by then never reached it.
IN_FLIGHT_GRACE = timedelta(minutes=30)

_DECLINED = "The payment gateway declined the transfer."
_BELOW_FEE = "The adjusted amount leaves nothing to pay after the transfer fee."
_NEVER_RECEIVED = "The payment gateway has no record of the transfer."
_UNRESOLVED_ACCOUNT = "The bank account was never checked with a live gateway; the agent must add it again."
_NARRATION = "Veriprops payout"


class _Unknown:
    """The gateway could not be asked: nothing can be concluded about the transfer."""


UNKNOWN = _Unknown()
Lookup = Union[GatewayTransfer, None, _Unknown]


# Where a transfer webhook may still move a payout: in flight, paid (a reversal), or failed by a
# reconcile that gave up before the transfer landed.
_SETTLEABLE = (PayoutStatus.PROCESSING.value, PayoutStatus.PAID.value, PayoutStatus.FAILED.value)


def _unpayable_reason(payout: Payout) -> Optional[str]:
    """Why a claimed payout cannot become a transfer at all, if it cannot."""
    if not payout.bank_code:
        return _UNRESOLVED_ACCOUNT
    if net_minor(payout) <= 0:
        return _BELOW_FEE
    return None


def transfer_reference_for(payout_id: Any, attempt: int) -> str:
    """Our reference for one transfer attempt: lowercase, and unique per attempt."""
    return f"vp-po-{uuid.UUID(str(payout_id)).hex}-{attempt}"


@inject
class PayoutDisbursementService:
    def __init__(self, payout_repo: PayoutRepo, gateway_factory: PaymentGatewayFactory, audit_service: AuditLogService):
        self._payout_repo = payout_repo
        self._gateways = gateway_factory
        self._audit = audit_service

    async def run(self, limit: int = DISBURSEMENT_BATCH_SIZE, actor_id: Optional[str] = None) -> DisbursementOutcomeDto:
        """Settle transfers left in flight, then send approved payouts, oldest decision first.

        ``actor_id`` is the finance user who pressed "disburse" (``None`` for the sweep); each
        transfer's audit names them. One payout's failure never stops the rest of the batch."""
        outcome = DisbursementOutcomeDto()
        stale = Utils.datetime_now() - IN_FLIGHT_GRACE
        for payout_id in await self._ids(PayoutStatus.PROCESSING, limit, stale):
            await self._guarded(self._reconcile(payout_id, outcome), payout_id, outcome)
        for payout_id in await self._ids(PayoutStatus.APPROVED, limit):
            await self._guarded(self._disburse(payout_id, outcome, actor_id), payout_id, outcome)
        outcome.remaining = await self._count(PayoutStatus.APPROVED)
        return outcome

    async def settle_from_gateway(self, reference: str) -> None:
        """A gateway's transfer webhook: look the transfer up and settle the attempt it names.

        A reference that is no payout's current attempt is ignored. A gateway that cannot be
        asked raises, so the webhook fails and the gateway sends it again."""
        payout = await self._find(reference)
        # FAILED too: a transfer reconcile gave up on can still land, and must then be PAID —
        # otherwise finance's retry would pay the agent a second time.
        if payout is None or payout.status not in _SETTLEABLE:
            return
        transfer = await self._gateway_for(payout).get_transfer(reference)
        if transfer is not None:
            await self._settle(payout.id, reference, transfer)

    # ── one payout ───────────────────────────────────────────────

    async def _guarded(self, step: Awaitable[None], payout_id: Any, outcome: DisbursementOutcomeDto) -> None:
        """Run one payout's step; a fault in it is logged and counted, never the batch's end.

        The payout is left where the fault found it — a claimed one stays PROCESSING, which a
        later run looks up — so nothing here can release or resend money."""
        try:
            await step
        except Exception:
            logger.exception(f"Payout {payout_id} could not be disbursed; it is left for the next run")
            outcome.in_flight += 1

    async def _disburse(self, payout_id: Any, outcome: DisbursementOutcomeDto, actor_id: Optional[str] = None) -> None:
        payout = await self._claim(payout_id, actor_id)
        if payout is None:
            return  # decided or claimed by someone else since it was listed
        reference = payout.transfer_reference
        unpayable = _unpayable_reason(payout)
        if unpayable:
            self._count_into(outcome, await self._fail(payout.id, reference, unpayable))
            return
        try:
            gateway = self._gateway_for(payout)
        except IntegrationFatalException:
            self._count_into(outcome, await self._fail(payout.id, reference, _UNRESOLVED_ACCOUNT))
            return
        request = TransferRequest(
            reference=reference, amount_minor=net_minor(payout), currency=TransactionCurrency(payout.currency),
            bank_code=payout.bank_code, account_number=payout.account_number,
            account_name=payout.account_name, narration=_NARRATION,
        )

        result: Lookup
        try:
            result = await gateway.send_transfer(request)
        except GatewayDeclined as declined:
            # A "no" may be the gateway refusing a reference it already took: look first.
            result = await self._look_up(gateway, reference)
            if result is None:
                reason = f"{_DECLINED} {declined.provider_message}" if declined.provider_message else _DECLINED
                self._count_into(outcome, await self._fail(payout.id, reference, reason))
                return
        except Exception:
            # Unreachable, a 5xx, or an answer we could not read: it may have landed.
            logger.exception(f"Payout transfer {reference} has an unknown outcome; looking it up")
            result = await self._look_up(gateway, reference)

        if isinstance(result, GatewayTransfer):
            self._count_into(outcome, await self._settle(payout.id, reference, result))
        else:
            # Unreachable, or answered nothing: it may have landed, so it stays in flight.
            outcome.in_flight += 1

    async def _reconcile(self, payout_id: Any, outcome: DisbursementOutcomeDto) -> None:
        payout = await self._get(payout_id)
        if payout is None or payout.status != PayoutStatus.PROCESSING.value or not payout.transfer_reference:
            return
        try:
            gateway = self._gateway_for(payout)
        except IntegrationFatalException:
            return
        result = await self._look_up(gateway, payout.transfer_reference)
        if isinstance(result, GatewayTransfer):
            self._count_into(outcome, await self._settle(payout.id, payout.transfer_reference, result))
        elif result is None:
            self._count_into(outcome, await self._fail(payout.id, payout.transfer_reference, _NEVER_RECEIVED))
        else:
            outcome.in_flight += 1

    async def _look_up(self, gateway: ITransferGateway, reference: str) -> Lookup:
        try:
            return await gateway.get_transfer(reference)
        except Exception:
            logger.exception(f"Payout transfer {reference} could not be looked up")
            return UNKNOWN

    def _gateway_for(self, payout: Payout) -> ITransferGateway:
        return self._gateways.transfers(platform_of(payout.provider))

    @staticmethod
    def _count_into(outcome: DisbursementOutcomeDto, status: Optional[PayoutStatus]) -> None:
        if status == PayoutStatus.PAID:
            outcome.paid += 1
        elif status == PayoutStatus.FAILED:
            outcome.failed += 1
        elif status == PayoutStatus.PROCESSING:
            outcome.in_flight += 1

    # ── writes: each commits on its own ───────────────────────────

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _claim(self, payout_id: Any, actor_id: Optional[str] = None) -> Optional[Payout]:
        """APPROVED → PROCESSING under the next attempt's reference, committed before any send."""
        payout = await self._payout_repo.get_model(payout_id)
        if payout is None or payout.deleted:
            return None
        attempt = (payout.transfer_attempts or 0) + 1
        reference = transfer_reference_for(payout.id, attempt)
        claimed = await self._payout_repo.claim_transition(
            payout.id, [PayoutStatus.APPROVED.value], PayoutStatus.PROCESSING,
            expect={"transfer_attempts": payout.transfer_attempts},
            transfer_reference=reference, transfer_attempts=attempt, gateway_transfer_id=None,
            sent_at=Utils.datetime_now(), settled_at=None, failure_reason=None,
        )
        if claimed is not None:
            self._audit.schedule(
                action=AuditActionType.PAYOUT_TRANSFER_SENT, resource_type="payout", resource_id=payout.id,
                actor_id=actor_id, from_state=PayoutStatus.APPROVED.value, to_state=PayoutStatus.PROCESSING.value,
                details={"reference": reference, "attempt": attempt, "net_minor": net_minor(payout)},
            )
        return claimed

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _settle(self, payout_id: Any, reference: str, transfer: GatewayTransfer) -> Optional[PayoutStatus]:
        """Apply what the gateway reports for *reference*; the payout's status afterwards, or
        ``None`` when the report no longer applies (another attempt, or already settled)."""
        if transfer.status == GatewayTransferStatus.FAILED:
            return await self._fail(payout_id, reference, transfer.failure_reason or _DECLINED,
                                    gateway_transfer_id=transfer.gateway_transfer_id)
        if transfer.status == GatewayTransferStatus.PENDING:
            noted = await self._payout_repo.claim_transition(
                payout_id, [PayoutStatus.PROCESSING.value], expect={"transfer_reference": reference},
                gateway_transfer_id=transfer.gateway_transfer_id,
            )
            return PayoutStatus.PROCESSING if noted is not None else None

        paid = await self._payout_repo.claim_transition(
            payout_id, [PayoutStatus.PROCESSING.value, PayoutStatus.FAILED.value], PayoutStatus.PAID,
            expect={"transfer_reference": reference},
            gateway_transfer_id=transfer.gateway_transfer_id, settled_at=Utils.datetime_now(), failure_reason=None,
        )
        if paid is None:
            return None
        self._audit.schedule(
            action=AuditActionType.PAYOUT_PAID, resource_type="payout", resource_id=payout_id,
            to_state=PayoutStatus.PAID.value,
            details={"reference": reference, "gateway_transfer_id": transfer.gateway_transfer_id},
        )
        await publish_domain_event(DomainEvent(type=EventType.PAYOUT_PAID, recipient_user_ids=(paid.agent_id,)))
        return PayoutStatus.PAID

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _fail(
        self, payout_id: Any, reference: str, reason: str, gateway_transfer_id: Optional[str] = None,
    ) -> Optional[PayoutStatus]:
        """PROCESSING (or PAID, for a reversal) → FAILED, funds still reserved, for finance."""
        values = {} if gateway_transfer_id is None else {"gateway_transfer_id": gateway_transfer_id}
        failed = await self._payout_repo.claim_transition(
            payout_id, [PayoutStatus.PROCESSING.value, PayoutStatus.PAID.value], PayoutStatus.FAILED,
            expect={"transfer_reference": reference}, failure_reason=reason, **values,
        )
        if failed is None:
            return None
        logger.warning(f"Payout transfer {reference} failed: {reason}")
        self._audit.schedule(
            action=AuditActionType.PAYOUT_TRANSFER_FAILED, resource_type="payout", resource_id=payout_id,
            to_state=PayoutStatus.FAILED.value, details={"reference": reference, "reason": reason},
        )
        return PayoutStatus.FAILED

    # ── reads ────────────────────────────────────────────────────

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _ids(self, status: PayoutStatus, limit: int, sent_before=None) -> list:
        return await self._payout_repo.ids_in_status(status, limit, sent_before)

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _count(self, status: PayoutStatus) -> int:
        return await self._payout_repo.count_in_status(status)

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _get(self, payout_id: Any) -> Optional[Payout]:
        return await self._payout_repo.get_model(payout_id)

    @transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
    async def _find(self, reference: str) -> Optional[Payout]:
        return await self._payout_repo.get_by_transfer_reference(reference)
