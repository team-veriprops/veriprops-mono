"""Refund requests (PRD §8.5, §18.1): every return of a customer's money waits for Finance.

A refund leaves the business's account and cannot be taken back, so nothing sends one on its
own authority. Whatever calls for a refund — closing a paid case, an upheld dispute, a charge
that landed on a case already closed — files a request here; a Finance (or super) admin
approves it, and only then does the money go back at the gateway. A rejected request sends
nothing.

One request may be pending per case at a time — a second would let the same money be asked for
twice — except late charges: each is its own charge, refunded by itself (`payment_id`).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Index, String, Text, text

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.db.types.money import TransactionCurrency


class RefundSource(str, enum.Enum):
    """What called for the refund."""

    CASE_CLOSURE = "CASE_CLOSURE"      # an admin closed a paid case (§6.4, the refund table)
    DISPUTE_UPHELD = "DISPUTE_UPHELD"  # a dispute resolved with a full refund (§14.3)
    LATE_CHARGE = "LATE_CHARGE"        # a charge that settled on a case already closed


class RefundRequestStatus(str, enum.Enum):
    PENDING = "PENDING"      # waiting for Finance
    APPROVED = "APPROVED"    # Finance approved; the refund was asked of the gateway
    REJECTED = "REJECTED"    # Finance declined; nothing was sent


# ─── ORM ──────────────────────────────────────────────────────────

class RefundRequest(BaseEntity):
    __tablename__ = "refund_requests"

    verification_id = Column(String(36), nullable=False)
    customer_id = Column(String(36), nullable=False)
    source = Column(String(24), nullable=False)
    status = Column(String(16), nullable=False, default=RefundRequestStatus.PENDING.value)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    # LATE_CHARGE only: the charge to return — that one, never the case's oldest.
    payment_id = Column(String(36), nullable=True)
    # Why, in the source's own terms: a closure's reason, or the dispute outcome.
    reason = Column(String(32), nullable=True)
    note = Column(Text, nullable=True)
    # What an admin-entered amount rests on (the inaccessible-property proof).
    evidence_ref = Column(String(255), nullable=True)
    requested_by = Column(String(36), nullable=True)   # None: filed by the system (a late charge)
    decided_by = Column(String(36), nullable=True)
    decided_at = Column(UTCDateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    # What the refund actually did is recorded on the charges it moved (refunded / still owed),
    # never here: a write after the money left could roll back and leave the two disagreeing.

    __table_args__ = (
        Index("ix_refund_requests_verification_id", "verification_id"),
        Index("ix_refund_requests_status_date_created", "status", "date_created"),
        # One pending request per case: the same money cannot be asked for twice. A late
        # charge is its own money, so each one waits separately.
        Index(
            "uq_refund_requests_pending_verification", "verification_id",
            unique=True,
            postgresql_where=text("status = 'PENDING' AND source <> 'LATE_CHARGE' AND deleted = FALSE"),
        ),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateRefundRequestDto(Object):
    verification_id: str
    customer_id: str
    source: RefundSource
    status: RefundRequestStatus = RefundRequestStatus.PENDING
    amount_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN
    payment_id: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    requested_by: Optional[str] = None


class UpdateRefundRequestDto(Object):
    status: Optional[RefundRequestStatus] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None


class SearchRefundRequestDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class QueryRefundRequestDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class DecideRefundRequestDto(Object):
    """Finance's decision. A note is required to reject: the requester and the customer are
    told why nothing was sent."""

    note: Optional[str] = None


class RefundRequestDto(Object):
    id: str
    verification_id: str
    vid: str
    customer_id: str
    source: RefundSource
    status: RefundRequestStatus
    amount_minor: int
    currency: TransactionCurrency
    reason: Optional[str] = None
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    requested_by: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    date_created: datetime
