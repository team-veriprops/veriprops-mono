"""Payout (agent withdrawal) domain (PRD §15.1).

An agent withdraws cleared earnings (§15.2) to one of their saved, bank-resolved accounts.
A request draws down the available balance and enters REQUESTED, with the gateway's
transfer fee quoted and deducted from what reaches the bank. Finance approves (→ APPROVED,
queued), holds, adjusts or rejects; approved payouts leave as bank transfers in a batch
(→ PROCESSING → PAID), from a daily sweep or finance's "disburse" button. A transfer the
bank refuses becomes FAILED with its funds still reserved, for finance to retry or reject.
Every action is audited and notified (§12.2). A 2-business-day SLA is stamped at request
time. Money is in integer minor units, NGN-contractual (§4.4).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import BigInteger, Column, Integer, String, Text

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.db.types.money import TransactionCurrency


class PayoutStatus(str, enum.Enum):
    """Lifecycle of a withdrawal request (§15.1)."""

    REQUESTED = "REQUESTED"    # agent asked; funds reserved out of available
    APPROVED = "APPROVED"      # finance cleared; waiting for the next disbursement batch
    HELD = "HELD"              # finance paused pending review
    PROCESSING = "PROCESSING"  # transfer handed to the gateway; waiting for the bank
    PAID = "PAID"              # the bank took the transfer (terminal, positive)
    FAILED = "FAILED"          # the transfer failed; funds still reserved until finance decides
    REJECTED = "REJECTED"      # finance declined; funds released (terminal)
    CANCELLED = "CANCELLED"    # agent withdrew the request; funds released (terminal)


# Statuses that still reserve funds out of the available balance (not yet released/paid out).
LOCKING_STATUSES = [
    PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value, PayoutStatus.HELD.value,
    PayoutStatus.PROCESSING.value, PayoutStatus.FAILED.value,
]
# Terminal statuses that release the reservation back to available.
RELEASED_STATUSES = [PayoutStatus.REJECTED.value, PayoutStatus.CANCELLED.value]


class PayoutAction(str, enum.Enum):
    """A move a person can make on a payout. Transfers move it the rest of the way."""

    APPROVE = "APPROVE"
    HOLD = "HOLD"
    ADJUST = "ADJUST"
    REJECT = "REJECT"
    RETRY = "RETRY"      # a failed transfer goes back into the next batch
    CANCEL = "CANCEL"    # the agent withdraws their own request


# The statuses each action starts from. The service claims its move from exactly these, and a
# DTO lists an action only while its payout is in one of them, so a screen never offers a
# move the backend would refuse. Nothing touches a payout while its transfer is in flight.
ACTION_FROM_STATUSES: Dict[PayoutAction, List[str]] = {
    PayoutAction.APPROVE: [PayoutStatus.REQUESTED.value, PayoutStatus.HELD.value],
    PayoutAction.HOLD: [PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value],
    PayoutAction.ADJUST: [
        PayoutStatus.REQUESTED.value, PayoutStatus.HELD.value,
        PayoutStatus.APPROVED.value, PayoutStatus.FAILED.value,
    ],
    PayoutAction.REJECT: [
        PayoutStatus.REQUESTED.value, PayoutStatus.HELD.value,
        PayoutStatus.APPROVED.value, PayoutStatus.FAILED.value,
    ],
    PayoutAction.RETRY: [PayoutStatus.FAILED.value],
    PayoutAction.CANCEL: [PayoutStatus.REQUESTED.value],
}
FINANCE_ACTIONS = [PayoutAction.APPROVE, PayoutAction.HOLD, PayoutAction.ADJUST, PayoutAction.REJECT, PayoutAction.RETRY]
AGENT_ACTIONS = [PayoutAction.CANCEL]


# Actions that end in a transfer. A payout from before accounts carried a bank code can never
# become one, so it is offered only the actions that settle it another way.
_SENDS_MONEY = {PayoutAction.APPROVE, PayoutAction.RETRY}


def allowed_actions(p: "Payout", audience: List[PayoutAction]) -> List[PayoutAction]:
    return [
        a for a in audience
        if p.status in ACTION_FROM_STATUSES[a] and (p.bank_code or a not in _SENDS_MONEY)
    ]


def platform_of(provider: Optional[str]) -> Optional[IntegratedPlatform]:
    """The gateway a stored ``provider`` names; ``None`` for one resolved under the stub."""
    return IntegratedPlatform(provider) if provider else None


# ─── ORM ──────────────────────────────────────────────────────────

class Payout(BaseEntity):
    __tablename__ = "payouts"

    agent_id = Column(String(36), nullable=False, index=True)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    status = Column(String(16), nullable=False, default=PayoutStatus.REQUESTED.value, index=True)
    # Beneficiary snapshot (copied at request so history is stable if the stored account changes).
    bank_name = Column(String(128), nullable=False)
    account_number = Column(String(32), nullable=False)
    account_name = Column(String(128), nullable=False)
    # The gateway's code for the bank, and the gateway that resolved the account (None under
    # the stub). A bank code is only meaningful to the gateway whose list it came from.
    bank_code = Column(String(16), nullable=True)
    provider = Column(String(32), nullable=True)

    requested_at = Column(UTCDateTime, nullable=True)
    sla_due_at = Column(UTCDateTime, nullable=True)     # 2-business-day payout SLA (§15.1)
    decided_at = Column(UTCDateTime, nullable=True)
    decided_by = Column(String(36), nullable=True)      # finance admin user id
    # Finance adjustment applied at approval (e.g. a correction), in minor units.
    adjustment_minor = Column(BigInteger, nullable=False, default=0)
    # The gateway's transfer fee, quoted at request and deducted from what reaches the bank.
    fee_minor = Column(BigInteger, nullable=False, default=0)
    note = Column(Text, nullable=True)                  # finance note / hold reason

    # The current transfer attempt: our reference (one per attempt, so a retry can never be
    # mistaken for the transfer it replaces), and the gateway's own id for it.
    transfer_reference = Column(String(64), nullable=True, unique=True, index=True)
    gateway_transfer_id = Column(String(64), nullable=True)
    transfer_attempts = Column(Integer, nullable=False, default=0)
    sent_at = Column(UTCDateTime, nullable=True)
    settled_at = Column(UTCDateTime, nullable=True)
    # The gateway's own words for a failed transfer: for finance, never for the agent.
    failure_reason = Column(Text, nullable=True)


def net_minor(p: Payout) -> int:
    """What reaches the agent's bank: the request, corrected by finance, less the fee."""
    return p.amount_minor + (p.adjustment_minor or 0) - (p.fee_minor or 0)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreatePayoutDto(Object):
    agent_id: str
    amount_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN
    status: PayoutStatus = PayoutStatus.REQUESTED
    bank_name: str
    bank_code: str
    provider: Optional[str] = None
    account_number: str
    account_name: str
    fee_minor: int


class UpdatePayoutDto(Object):
    status: Optional[str] = None
    decided_by: Optional[str] = None
    adjustment_minor: Optional[int] = None
    note: Optional[str] = None


class QueryPayoutDto(BaseQueryDto):
    agent_id: Optional[str] = None
    status: Optional[str] = None


class SearchPayoutDto(InternalPageRequest, BaseQueryDto):
    agent_id: Optional[str] = None
    status: Optional[str] = None


class RequestPayoutDto(Object):
    """Agent withdrawal request, to one of their saved bank-resolved accounts."""

    amount_minor: int
    bank_account_id: str


class QuotePayoutDto(Object):
    amount_minor: int
    bank_account_id: str


class PayoutQuoteDto(Object):
    """What a withdrawal of ``amount_minor`` costs, and what reaches the bank."""

    amount_minor: int
    fee_minor: int
    net_minor: int


class PayoutDecisionDto(Object):
    """Finance decision inputs (hold reason / adjustment note)."""

    note: Optional[str] = None
    adjustment_minor: Optional[int] = None


class PayoutDto(Object):
    id: str
    agent_id: str
    amount_minor: int
    fee_minor: int = 0
    net_minor: int
    currency: TransactionCurrency
    status: PayoutStatus
    bank_name: str
    account_number: str
    account_name: str
    adjustment_minor: int = 0
    note: Optional[str] = None
    requested_at: Optional[datetime] = None
    sla_due_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    date_created: datetime
    allowed_actions: List[PayoutAction] = []


class AdminPayoutDto(PayoutDto):
    """A payout as finance sees it: the transfer's trail, and why it failed."""

    bank_code: Optional[str] = None
    provider: Optional[str] = None
    transfer_reference: Optional[str] = None
    gateway_transfer_id: Optional[str] = None
    transfer_attempts: int = 0
    sent_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class DisbursementQueueDto(Object):
    """Approved payouts waiting for the next batch, and the gateway balance they will draw
    (the fee comes out of what the agent receives, so it is inside this total). ``in_flight``
    counts transfers still with the bank, which a batch also looks up."""

    count: int
    total_minor: int
    in_flight: int = 0


class DisbursementOutcomeDto(Object):
    """What one disbursement run did."""

    paid: int = 0
    failed: int = 0
    in_flight: int = 0     # handed to the gateway, outcome not known yet
    remaining: int = 0     # still APPROVED: the batch limit was reached


def _base_fields(p: Payout) -> dict:
    return dict(
        id=p.id, agent_id=p.agent_id, amount_minor=p.amount_minor, fee_minor=p.fee_minor or 0,
        net_minor=net_minor(p), currency=TransactionCurrency(p.currency), status=PayoutStatus(p.status),
        bank_name=p.bank_name, account_number=p.account_number, account_name=p.account_name,
        adjustment_minor=p.adjustment_minor or 0, note=p.note,
        requested_at=p.requested_at, sla_due_at=p.sla_due_at, decided_at=p.decided_at,
        settled_at=p.settled_at, date_created=p.date_created,
    )


def payout_to_dto(p: Payout) -> PayoutDto:
    """A payout as its agent sees it."""
    return PayoutDto(**_base_fields(p), allowed_actions=allowed_actions(p, AGENT_ACTIONS))


def admin_payout_to_dto(p: Payout) -> AdminPayoutDto:
    """A payout as finance sees it."""
    return AdminPayoutDto(
        **_base_fields(p), allowed_actions=allowed_actions(p, FINANCE_ACTIONS),
        bank_code=p.bank_code, provider=p.provider, transfer_reference=p.transfer_reference,
        gateway_transfer_id=p.gateway_transfer_id, transfer_attempts=p.transfer_attempts or 0,
        sent_at=p.sent_at, failure_reason=p.failure_reason,
    )
