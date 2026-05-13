"""Referral domain models — Phase 17 (S51).

ReferralCode: one per customer, contains a unique 8-char slug.
ReferralRedemption: created when an invitee signs up via a referral link.
Status transitions: PENDING → CREDITED (after invitee completes first payment).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class RedemptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    CREDITED = "CREDITED"


# ─── ORM ──────────────────────────────────────────────────────────

class ReferralCode(BaseEntity):
    __tablename__ = "referral_codes"

    owner_id = Column(String(36), nullable=False, unique=True, index=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    times_redeemed = Column(Integer, nullable=False, default=0)


class ReferralRedemption(BaseEntity):
    __tablename__ = "referral_redemptions"

    referral_code_id = Column(String(36), nullable=False, index=True)
    invitee_id = Column(String(36), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=RedemptionStatus.PENDING.value)
    credited_at = Column(UTCDateTime, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class ReferralCodeDto(Object):
    id: str
    owner_id: str
    code: str
    times_redeemed: int
    referral_link: str
    date_created: datetime


class ReferralStatsDto(Object):
    code: str
    referral_link: str
    total_invited: int
    total_credited: int
    pending_count: int
    credit_balance_ngn: float


class ReferralRedemptionDto(Object):
    id: str
    referral_code_id: str
    invitee_id: str
    status: RedemptionStatus
    credited_at: Optional[datetime] = None
    date_created: datetime


class DiscountBreakdownDto(Object):
    """Breakdown of discounts applied to a payment amount."""
    original_amount_kobo: int
    first_time_discount_kobo: int
    referral_discount_kobo: int
    total_discount_kobo: int
    final_amount_kobo: int
    first_time_discount_percent: float
    referral_discount_applied: bool


# ─── Repo DTOs ────────────────────────────────────────────────────

class CreateReferralCodeDto(Object):
    owner_id: str
    code: str


class UpdateReferralCodeDto(Object):
    times_redeemed: Optional[int] = None


class QueryReferralCodeDto(BaseQueryDto):
    owner_id: Optional[str] = None
    code: Optional[str] = None


class SearchReferralCodeDto(PageRequest, BaseQueryDto):
    owner_id: Optional[str] = None


class CreateReferralRedemptionDto(Object):
    referral_code_id: str
    invitee_id: str
    status: str = RedemptionStatus.PENDING.value


class UpdateReferralRedemptionDto(Object):
    status: Optional[str] = None
    credited_at: Optional[datetime] = None


class QueryReferralRedemptionDto(BaseQueryDto):
    referral_code_id: Optional[str] = None
    invitee_id: Optional[str] = None
    status: Optional[str] = None


class SearchReferralRedemptionDto(PageRequest, BaseQueryDto):
    referral_code_id: Optional[str] = None


# ─── Request DTOs ────────────────────────────────────────────────

class ClaimReferralDto(Object):
    code: str
