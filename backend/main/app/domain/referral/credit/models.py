"""Referral-credit ledger (PRD §17.1, D35).

A ledger row is created when a referred invitee makes their first payment. It stays
**PENDING** until the invitee's payment passes the chargeback-window reserve (§15.2) —
the same clearance horizon commissions use — at which point it **CLEARS** and its amount
is added to the referrer's spendable ``credit_balance_kobo``. This closes the
refer-then-charge-back loop: a credit never pays out before the referred payment is safe.
An anti-farming rejection (same verified human) records a **VOID** row instead.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


class ReferralCreditStatus(str, enum.Enum):
    """Lifecycle of a referral credit (PRD §17.1)."""

    PENDING = "PENDING"    # invitee has paid; held through the chargeback window
    CLEARED = "CLEARED"    # window passed; amount added to the referrer's balance
    VOID = "VOID"          # anti-farming rejection or reversal — never pays out


# ─── ORM ──────────────────────────────────────────────────────────

class ReferralCredit(BaseEntity):
    __tablename__ = "referral_credits"

    referrer_user_id = Column(String(36), nullable=False, index=True)
    invitee_user_id = Column(String(36), nullable=False, index=True)
    verification_id = Column(String(36), nullable=False, index=True)

    amount_minor = Column(BigInteger, nullable=False)
    status = Column(String(16), nullable=False, default=ReferralCreditStatus.PENDING.value, index=True)
    # When a PENDING credit clears to the referrer's balance (invitee paid_at + chargeback window).
    clearing_until = Column(UTCDateTime, nullable=True)
    # Set once the credit has cleared (idempotency marker for the sweep).
    cleared_at = Column(UTCDateTime, nullable=True)
    # Recorded reason for a VOID row (e.g. anti-farming: same verified human).
    void_reason = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_referral_credits_referrer", "referrer_user_id"),
        Index("ix_referral_credits_invitee", "invitee_user_id"),
        # status index is declared inline (index=True) → ix_referral_credits_status.
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateReferralCreditDto(Object):
    referrer_user_id: str
    invitee_user_id: str
    verification_id: str
    amount_minor: int
    status: ReferralCreditStatus = ReferralCreditStatus.PENDING
    clearing_until: Optional[datetime] = None
    void_reason: Optional[str] = None


class UpdateReferralCreditDto(Object):
    status: Optional[str] = None
    void_reason: Optional[str] = None


class QueryReferralCreditDto(BaseQueryDto):
    referrer_user_id: Optional[str] = None
    invitee_user_id: Optional[str] = None
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchReferralCreditDto(InternalPageRequest, BaseQueryDto):
    referrer_user_id: Optional[str] = None
    status: Optional[str] = None


class ReferralCreditDto(Object):
    id: str
    invitee_user_id: str
    verification_id: str
    amount_minor: int
    status: ReferralCreditStatus
    clearing_until: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    date_created: datetime
