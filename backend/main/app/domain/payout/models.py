"""Payout (agent withdrawal) domain (PRD §15.1).

An agent withdraws cleared earnings (§15.2) to a bank beneficiary. A request draws down
the available balance and enters REQUESTED; Finance approves (→ PAID, stub disbursement),
holds, adjusts, or rejects — every action audited and notified (§12.2). A 2-business-day
SLA is stamped at request time. Money is in integer minor units, NGN-contractual (§4.4).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.db.types.money import TransactionCurrency


class PayoutStatus(str, enum.Enum):
    """Lifecycle of a withdrawal request (§15.1)."""

    REQUESTED = "REQUESTED"    # agent asked; funds reserved out of available
    APPROVED = "APPROVED"      # finance cleared; disbursement issued (stub)
    HELD = "HELD"              # finance paused pending review
    PAID = "PAID"             # disbursed (terminal, positive)
    REJECTED = "REJECTED"      # finance declined; funds released (terminal)
    CANCELLED = "CANCELLED"    # agent withdrew the request; funds released (terminal)


# Statuses that still reserve funds out of the available balance (not yet released/paid out).
LOCKING_STATUSES = [PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value, PayoutStatus.HELD.value]
# Terminal statuses that release the reservation back to available.
RELEASED_STATUSES = [PayoutStatus.REJECTED.value, PayoutStatus.CANCELLED.value]


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

    requested_at = Column(UTCDateTime, nullable=True)
    sla_due_at = Column(UTCDateTime, nullable=True)     # 2-business-day payout SLA (§15.1)
    decided_at = Column(UTCDateTime, nullable=True)
    decided_by = Column(String(36), nullable=True)      # finance admin user id
    # Finance adjustment applied at approval (e.g. a correction), in minor units.
    adjustment_minor = Column(BigInteger, nullable=False, default=0)
    note = Column(Text, nullable=True)                  # finance note / hold reason


# ─── DTOs ─────────────────────────────────────────────────────────

class CreatePayoutDto(Object):
    agent_id: str
    amount_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN
    status: PayoutStatus = PayoutStatus.REQUESTED
    bank_name: str
    account_number: str
    account_name: str


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
    """Agent withdrawal request — either a stored ``bank_account_id`` or a one-time entry."""

    amount_minor: int
    bank_account_id: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None


class PayoutDecisionDto(Object):
    """Finance decision inputs (hold reason / adjustment note)."""

    note: Optional[str] = None
    adjustment_minor: Optional[int] = None


class PayoutDto(Object):
    id: str
    agent_id: str
    amount_minor: int
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
    date_created: datetime


def payout_to_dto(p: Payout) -> PayoutDto:
    return PayoutDto(
        id=p.id, agent_id=p.agent_id, amount_minor=p.amount_minor,
        currency=TransactionCurrency(p.currency), status=PayoutStatus(p.status),
        bank_name=p.bank_name, account_number=p.account_number, account_name=p.account_name,
        adjustment_minor=p.adjustment_minor or 0, note=p.note,
        requested_at=p.requested_at, sla_due_at=p.sla_due_at, decided_at=p.decided_at,
        date_created=p.date_created,
    )
