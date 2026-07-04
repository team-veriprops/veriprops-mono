"""Chargeback domain (PRD §6a).

A chargeback is a **gateway/bank-side** financial dispute — distinct from the
customer ``DISPUTED`` verification flow (§14). It is modelled as a flag + sub-process
on the payment (§6a.1), **never** a verification state: bank-side states Veriprops
does not control never enter the verification state machine. Each chargeback carries
the auto-assembled rebuttal pack (§6a.2) compiled from existing audit artefacts.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT
from main.appodus_utils.db.types.money import TransactionCurrency


class ChargebackStatus(str, enum.Enum):
    """Chargeback sub-process lifecycle (PRD §6a.2). Outcome is network-controlled."""

    FLAGGED = "FLAGGED"                        # webhook arrived; commissions frozen
    REBUTTAL_SUBMITTED = "REBUTTAL_SUBMITTED"  # admin submitted the pack to the gateway
    WON = "WON"                                # payment restored; commissions resume
    LOST = "LOST"                              # payment reversed; commissions clawed back


# ─── ORM ──────────────────────────────────────────────────────────

class Chargeback(BaseEntity):
    __tablename__ = "chargebacks"

    payment_id = Column(String(36), nullable=False, index=True)
    verification_id = Column(String(36), nullable=False, index=True)
    # Gateway event id — idempotency key so a replayed chargeback webhook is a no-op (§4.6).
    gateway_event_id = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(24), nullable=False, default=ChargebackStatus.FLAGGED.value, index=True)
    reason = Column(String(500), nullable=True)
    amount_minor = Column(BigInteger, nullable=True)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    # Auto-assembled rebuttal pack (§6a.2): consent records, report, audit trail,
    # evidence hashes, payment/receipt — a self-contained submission snapshot.
    rebuttal_pack = Column(JSONB_VARIANT, nullable=True)
    resolved_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_chargebacks_payment", "payment_id"),
        Index("ix_chargebacks_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateChargebackDto(Object):
    payment_id: str
    verification_id: str
    gateway_event_id: str
    status: ChargebackStatus = ChargebackStatus.FLAGGED
    reason: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: TransactionCurrency = TransactionCurrency.NGN
    rebuttal_pack: Optional[Dict[str, Any]] = None


class UpdateChargebackDto(Object):
    status: Optional[str] = None
    reason: Optional[str] = None
    rebuttal_pack: Optional[Dict[str, Any]] = None


class SearchChargebackDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: Optional[str] = None


class QueryChargebackDto(BaseQueryDto):
    payment_id: Optional[str] = None
    verification_id: Optional[str] = None
    gateway_event_id: Optional[str] = None
    status: Optional[str] = None


# ─── API / webhook DTOs ───────────────────────────────────────────

class ChargebackWebhookDto(Object):
    """Provider-agnostic chargeback webhook (§4.6) keyed on the gateway event id."""

    event_id: str
    tx_ref: str
    reason: Optional[str] = None
    amount_minor: Optional[int] = None


class ResolveChargebackDto(Object):
    won: bool


class ChargebackDto(Object):
    id: str
    payment_id: str
    verification_id: str
    status: ChargebackStatus
    reason: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: TransactionCurrency
    rebuttal_pack: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    date_created: datetime
