"""Payment domain (PRD §4.4, §4.6, §5.4).

Gateway-mediated collection; the platform never handles raw card/bank data. The
gateway webhook (idempotent on the gateway event id) drives PAYMENT_PENDING → PAID.
Payment initiation takes a client idempotency key (double-tap protection).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Index, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.types.money import TransactionCurrency


class PaymentStatus(str, enum.Enum):
    """Plain-language statuses surfaced to the customer (never raw gateway codes)."""

    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PENDING_TRANSFER = "PENDING_TRANSFER"
    REFUNDED = "REFUNDED"


class PaymentMethodKind(str, enum.Enum):
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"


class PaymentPurpose(str, enum.Enum):
    """What a charge is for, so the idempotent webhook routes a confirmed payment to the
    right post-payment handler (§5.4 initial vs §14.1 re-check vs §14.2 tier upgrade)."""

    INITIAL = "INITIAL"
    RECHECK = "RECHECK"
    UPGRADE = "UPGRADE"


class Payment(BaseEntity):
    __tablename__ = "payments"

    verification_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    # What the charge is for (§14) — routes the confirmed webhook to the right handler.
    purpose = Column(String(16), nullable=False, default=PaymentPurpose.INITIAL.value)
    tx_ref = Column(String(64), nullable=False, unique=True, index=True)
    # Gateway event id — the idempotency key for webhook processing (§4.6).
    gateway_event_id = Column(String(128), nullable=True, index=True)
    provider = Column(String(32), nullable=True)
    method = Column(String(16), nullable=False)
    status = Column(String(20), nullable=False, default=PaymentStatus.INITIATED.value)

    # Contractual NGN amount (kobo) + how the customer actually paid.
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    charge_currency = Column(String(8), nullable=True)
    charge_amount_minor = Column(BigInteger, nullable=True)

    checkout_url = Column(String(1024), nullable=True)
    failure_count = Column(Integer, nullable=False, server_default="0")
    # Chargeback flag (§6a.1) — the sub-process detail lives on the Chargeback row;
    # this column marks the payment so lists/detail can surface it. Null = none.
    chargeback_status = Column(String(24), nullable=True)
    refunded_amount_minor = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index("ix_payments_verification", "verification_id"),
        Index("ix_payments_gateway_event", "gateway_event_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreatePaymentDto(Object):
    verification_id: str
    customer_id: str
    tx_ref: str
    method: PaymentMethodKind
    purpose: PaymentPurpose = PaymentPurpose.INITIAL
    amount_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN
    charge_currency: Optional[TransactionCurrency] = None
    charge_amount_minor: Optional[int] = None
    provider: Optional[str] = None
    status: PaymentStatus = PaymentStatus.INITIATED
    checkout_url: Optional[str] = None


class UpdatePaymentDto(Object):
    status: Optional[str] = None
    gateway_event_id: Optional[str] = None
    provider: Optional[str] = None
    checkout_url: Optional[str] = None
    failure_count: Optional[int] = None
    chargeback_status: Optional[str] = None
    refunded_amount_minor: Optional[int] = None


class SearchPaymentDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None


class QueryPaymentDto(BaseQueryDto):
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
    tx_ref: Optional[str] = None
    status: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class InitiatePaymentDto(Object):
    method: PaymentMethodKind = PaymentMethodKind.CARD


class PaymentDto(Object):
    id: str
    verification_id: str
    tx_ref: str
    method: PaymentMethodKind
    purpose: PaymentPurpose = PaymentPurpose.INITIAL
    status: PaymentStatus
    amount_minor: int
    currency: TransactionCurrency
    charge_currency: Optional[TransactionCurrency] = None
    charge_amount_minor: Optional[int] = None
    checkout_url: Optional[str] = None
    date_created: datetime


class PaymentWebhookDto(Object):
    """Provider-agnostic webhook payload (§4.6) keyed on the gateway event id."""

    event_id: str
    tx_ref: str
    succeeded: bool
