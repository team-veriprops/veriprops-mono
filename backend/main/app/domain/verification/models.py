"""Verification domain (PRD §2.1, §4.3, §4.4, §5).

The central aggregate: points at a Property, carries the tier, the derived global
``status``, the money fields (NGN-contractual vs. how the customer paid), the 24h
price lock, the consent snapshot, and the SLA due date. The resumable wizard state
(draft step + payload) lives on the row — the VID/DRAFT is created on step-1 load.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, Date, Float, Integer, String, Text

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.db.types.money import TransactionCurrency
from main.app.domain.property.models import PropertyInputDto


class Verification(BaseEntity):
    __tablename__ = "verifications"

    vid = Column(String(16), nullable=False, unique=True, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    property_id = Column(String(36), nullable=True, index=True)
    tier = Column(String(16), nullable=True)
    status = Column(String(20), nullable=False, default=VerificationStatus.DRAFT.value, index=True)

    # Money (PRD §4.4). Contractual amount is always NGN, in kobo.
    price_locked_minor = Column(BigInteger, nullable=True)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    charge_currency = Column(String(8), nullable=True)
    charge_amount_minor = Column(BigInteger, nullable=True)
    fx_rate_at_quote = Column(Float, nullable=True)
    price_lock_expires_at = Column(UTCDateTime, nullable=True)

    # Growth discounts (§17.1) recorded at submit, in NGN kobo. price_locked_minor is the
    # NET (post-discount) contractual amount actually charged. These break it down for the
    # customer and drive the referral-credit debit at PAID.
    first_time_discount_minor = Column(BigInteger, nullable=False, server_default="0")
    referral_credit_applied_minor = Column(BigInteger, nullable=False, server_default="0")

    consent_snapshot_id = Column(String(36), nullable=True)

    # Resumable wizard state (VID/DRAFT created on step-1 load, autosaved per step).
    draft_step = Column(Integer, nullable=False, server_default="0")
    draft_payload = Column(Text, nullable=True)

    paid_at = Column(UTCDateTime, nullable=True)
    sla_due_date = Column(Date, nullable=True)

    # Abandoned-draft recovery (§17.1): set the first time a recovery reminder fires so the
    # email is sent exactly once per abandoned draft; also flips the customer-facing banner.
    recovery_reminded_at = Column(UTCDateTime, nullable=True)

    # Admin operational hold (§7.5) — a flag, NOT a state: the derived status is
    # unaffected so work resumes cleanly. Set/cleared by the admin control panel.
    paused = Column(Boolean, nullable=False, server_default="false")

    # Public VID-lookup visibility (§13.1/§13.2 "Public" mode): when true, anyone who
    # knows the VID sees the report *summary* at /verify/{vid}. Default private.
    public_lookup_enabled = Column(Boolean, nullable=False, server_default="false")

    # Why the next report release should bump the version (§14): a re-check sets RECHECK,
    # a tier upgrade sets TIER_UPGRADE. Consumed + cleared by ReviewService.release. Null =
    # the ordinary initial release (v1.0).
    pending_revision_kind = Column(String(16), nullable=True)
    # customer_id / status indexes are declared inline (index=True) — they
    # auto-name to ix_verifications_customer_id / ix_verifications_status,
    # matching the migration. Don't re-declare them here.


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateVerificationDto(Object):
    vid: str
    customer_id: str
    status: VerificationStatus = VerificationStatus.DRAFT


class UpdateVerificationDto(Object):
    property_id: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None
    price_locked_minor: Optional[int] = None
    currency: Optional[str] = None
    charge_currency: Optional[str] = None
    charge_amount_minor: Optional[int] = None
    fx_rate_at_quote: Optional[float] = None
    first_time_discount_minor: Optional[int] = None
    referral_credit_applied_minor: Optional[int] = None
    consent_snapshot_id: Optional[str] = None
    draft_step: Optional[int] = None
    draft_payload: Optional[str] = None
    public_lookup_enabled: Optional[bool] = None
    pending_revision_kind: Optional[str] = None


class SearchVerificationDto(InternalPageRequest, BaseQueryDto):
    customer_id: Optional[str] = None
    status: Optional[str] = None


class QueryVerificationDto(BaseQueryDto):
    vid: Optional[str] = None
    customer_id: Optional[str] = None
    property_id: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class SaveVerificationDraftDto(Object):
    step: int
    payload: dict


class VerificationConsentDto(Object):
    consent_version: str


class SubmitVerificationDto(Object):
    """Finalise the submission (property + tier + consent) → SUBMITTED (PRD §5.6)."""

    property: PropertyInputDto
    tier: VerificationTier
    currency: TransactionCurrency = TransactionCurrency.NGN
    consent: VerificationConsentDto


class PriceQuoteDto(Object):
    tier: VerificationTier
    price_ngn_minor: int
    currency: TransactionCurrency
    charge_amount_minor: int
    fx_rate: float
    # Growth discounts (§17.1, §5.2) — all in NGN kobo. ``net_price_ngn_minor`` is what the
    # customer will actually be charged; the breakdown lines are shown in the quote.
    first_time_discount_minor: int = 0
    referral_credit_applied_minor: int = 0
    total_discount_minor: int = 0
    net_price_ngn_minor: int = 0
    discount_cap_hit: bool = False


class LineItemDto(Object):
    """A single itemized pricing line for a tier (§5.2, §18.1 pricing config)."""

    label: str
    amount_minor: int


class VerificationDto(Object):
    id: str
    vid: str
    status: VerificationStatus
    tier: Optional[VerificationTier] = None
    property_id: Optional[str] = None
    price_locked_minor: Optional[int] = None
    currency: TransactionCurrency = TransactionCurrency.NGN
    charge_currency: Optional[TransactionCurrency] = None
    charge_amount_minor: Optional[int] = None
    fx_rate_at_quote: Optional[float] = None
    price_lock_expires_at: Optional[datetime] = None
    first_time_discount_minor: int = 0
    referral_credit_applied_minor: int = 0
    paid_at: Optional[datetime] = None
    sla_due_date: Optional[date] = None
    draft_step: int = 0


class PriceRefreshDto(Object):
    """Result of re-locking an expired price before payment (§17.1 re-lock guard).

    ``price_changed`` drives the mandatory "price updated" interstitial — the customer is
    never silently charged a different amount than they last saw."""

    price_changed: bool
    previous_price_minor: int
    net_price_minor: int
    first_time_discount_minor: int
    referral_credit_applied_minor: int
    price_lock_expires_at: Optional[datetime] = None


class VerificationDraftDto(Object):
    id: str
    vid: str
    status: VerificationStatus
    step: int
    payload: dict
