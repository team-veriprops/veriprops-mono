"""Payment domain (PRD §4.4, §4.6, §5.4).

Gateway-mediated collection; the platform never handles raw card/bank data. The
gateway webhook (idempotent on the gateway event id) drives PAYMENT_PENDING → PAID.
Payment initiation takes a client idempotency key (double-tap protection).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Column, Index, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
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


class PaymentCheckoutKind(str, enum.Enum):
    """How the customer completes a charge, so the pay page never has to guess from a URL."""

    # Deterministic local/test/dev completion (PAYMENT_STUB_MODE): the pay page confirms it.
    STUB = "STUB"
    # The gateway's hosted page: the pay page sends the customer to ``checkout_url``.
    HOSTED = "HOSTED"


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
    # The IntegratedPlatform that holds the charge (None under PAYMENT_STUB_MODE).
    provider = Column(String(32), nullable=True)
    # The gateway's own handle for the charge (Flutterwave flw_ref, Paystack transaction id),
    # recorded when the charge is confirmed. Chargebacks that cite only it are matched by it.
    gateway_reference = Column(String(128), nullable=True, index=True)
    method = Column(String(16), nullable=False)
    status = Column(String(20), nullable=False, default=PaymentStatus.INITIATED.value)

    # Contractual NGN amount (kobo) + how the customer actually paid.
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    charge_currency = Column(String(8), nullable=True)
    charge_amount_minor = Column(BigInteger, nullable=True)

    checkout_url = Column(String(1024), nullable=True)
    # Anti-farming instrument marker (§17.1, D34) — a gateway-surfaced card fingerprint/
    # authorization token, never raw card data. Null under PAYMENT_STUB_MODE (no live
    # gateway); the referral anti-farming check reads it once the live gateway fills it in.
    # TODO(gap): capture stays dark until the live gateway populates it — PRD "Known Gaps & Roadmap".
    card_fingerprint = Column(String(128), nullable=True, index=True)
    failure_count = Column(Integer, nullable=False, server_default="0")
    # Chargeback flag (§6a.1) — the sub-process detail lives on the Chargeback row;
    # this column marks the payment so lists/detail can surface it. Null = none.
    chargeback_status = Column(String(24), nullable=True)
    refunded_amount_minor = Column(BigInteger, nullable=True)
    # What an approved refund still owes on this charge because its gateway refused it:
    # Finance's refunds-to-retry list, and exactly what a retry sends. None once paid back.
    refund_due_minor = Column(BigInteger, nullable=True)

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
    gateway_reference: Optional[str] = None
    provider: Optional[str] = None
    checkout_url: Optional[str] = None
    card_fingerprint: Optional[str] = None
    failure_count: Optional[int] = None
    chargeback_status: Optional[str] = None
    refunded_amount_minor: Optional[int] = None


class SearchPaymentDto(InternalPageRequest, BaseQueryDto):
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
    checkout_kind: PaymentCheckoutKind = PaymentCheckoutKind.STUB
    date_created: datetime


class AdminPaymentDto(PaymentDto):
    """One charge as finance reads it (§18.1): which case, which gateway, and where the money
    stands: refunded, or held under a chargeback."""

    vid: str
    customer_id: str
    provider: Optional[str] = None
    gateway_reference: Optional[str] = None
    refunded_amount_minor: Optional[int] = None
    # An approved refund the gateway refused, still owed: retry it from the refunds list.
    refund_due_minor: Optional[int] = None
    chargeback_status: Optional[str] = None


class RefundOutcome(Object):
    """What a verification's refund did: the total refunded, and the payments whose gateway
    refund was refused (still SUCCEEDED, listed for a finance retry)."""

    refunded_minor: int = 0
    failed_payment_ids: List[str] = []
    # Payments under a chargeback: the issuer is returning that money, so we do not.
    held_payment_ids: List[str] = []


def payment_to_dto(p: Payment) -> PaymentDto:
    return PaymentDto(
        id=p.id,
        verification_id=p.verification_id,
        tx_ref=p.tx_ref,
        method=p.method,
        purpose=p.purpose,
        status=p.status,
        amount_minor=p.amount_minor,
        currency=TransactionCurrency(p.currency),
        charge_currency=TransactionCurrency(p.charge_currency) if p.charge_currency else None,
        charge_amount_minor=p.charge_amount_minor,
        checkout_url=p.checkout_url,
        # A live charge has a provider; a stub charge completes on the pay page itself.
        checkout_kind=PaymentCheckoutKind.HOSTED if p.provider else PaymentCheckoutKind.STUB,
        date_created=p.date_created,
    )


class PaymentWebhookDto(Object):
    """Provider-agnostic webhook payload (§4.6) keyed on the gateway event id."""

    event_id: str
    tx_ref: str
    succeeded: bool


def admin_payment_to_dto(p: Payment, vid: str) -> AdminPaymentDto:
    return AdminPaymentDto(
        **payment_to_dto(p).model_dump(),
        vid=vid,
        customer_id=p.customer_id,
        provider=p.provider,
        gateway_reference=p.gateway_reference,
        refunded_amount_minor=p.refunded_amount_minor,
        refund_due_minor=p.refund_due_minor,
        chargeback_status=p.chargeback_status,
    )
