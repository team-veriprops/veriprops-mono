"""Verification domain (PRD §2.1, §4.3, §4.4, §5).

The central aggregate: points at a Property, carries the tier, the derived global
``status``, the money fields (NGN-contractual vs. how the customer paid), the 24h
price lock, the consent snapshot, and the SLA due date. The resumable wizard state
(draft step + payload) lives on the row — the VID/DRAFT is created on step-1 load.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Column, Date, Float, Index, Integer, String, Text

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
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

    consent_snapshot_id = Column(String(36), nullable=True)

    # Resumable wizard state (VID/DRAFT created on step-1 load, autosaved per step).
    draft_step = Column(Integer, nullable=False, server_default="0")
    draft_payload = Column(Text, nullable=True)

    paid_at = Column(UTCDateTime, nullable=True)
    sla_due_date = Column(Date, nullable=True)

    __table_args__ = (
        Index("ix_verifications_status", "status"),
        Index("ix_verifications_customer", "customer_id"),
    )


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
    consent_snapshot_id: Optional[str] = None
    draft_step: Optional[int] = None
    draft_payload: Optional[str] = None


class SearchVerificationDto(PageRequest, BaseQueryDto):
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
    paid_at: Optional[datetime] = None
    sla_due_date: Optional[date] = None
    draft_step: int = 0


class VerificationDraftDto(Object):
    id: str
    vid: str
    status: VerificationStatus
    step: int
    payload: dict
