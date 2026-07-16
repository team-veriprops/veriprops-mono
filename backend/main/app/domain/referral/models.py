"""Referral link domain (PRD §17.1).

Each user owns one shareable referral ``code``. A new signup that carries the code is
linked to the referrer (``users.referred_by``); the referrer earns ``referral_credit_ngn``
when the invitee's first payment clears the chargeback window (see ``referral/credit/``).
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest

from main.app.domain.referral.credit.models import ReferralCreditDto


class Referral(BaseEntity):
    __tablename__ = "referrals"

    referrer_user_id = Column(String(36), nullable=False, unique=True, index=True)
    code = Column(String(16), nullable=False, unique=True, index=True)

    __table_args__ = (
        Index("ix_referrals_referrer", "referrer_user_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateReferralDto(Object):
    referrer_user_id: str
    code: str


class UpdateReferralDto(Object):
    code: Optional[str] = None


class QueryReferralDto(BaseQueryDto):
    referrer_user_id: Optional[str] = None
    code: Optional[str] = None


class SearchReferralDto(InternalPageRequest, BaseQueryDto):
    referrer_user_id: Optional[str] = None
    code: Optional[str] = None


# ─── API response DTOs ────────────────────────────────────────────

class ReferralSummaryDto(Object):
    """The customer's referral link + credit balances (PRD §17.1, dashboard card)."""

    code: str
    share_path: str
    referral_credit_ngn: int          # the current per-referral reward (whole NGN)
    available_credit_minor: int       # spendable now (cleared), in kobo
    pending_credit_minor: int         # earned, awaiting clearance, in kobo
    lifetime_credit_minor: int        # total ever cleared, in kobo
    credits: List[ReferralCreditDto]
