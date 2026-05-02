"""Payment domain models — PRD Phase 5 / §5.4."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class PaymentProvider(str, enum.Enum):
    FLUTTERWAVE = "FLUTTERWAVE"
    PAYSTACK = "PAYSTACK"


class PaymentMethod(str, enum.Enum):
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    WIRE = "WIRE"


class PaymentStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PENDING_TRANSFER = "PENDING_TRANSFER"
    PENDING_WIRE = "PENDING_WIRE"


# ─── ORM ──────────────────────────────────────────────────────────


class Payment(BaseEntity):
    __tablename__ = "payments"

    verification_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(16), nullable=False, default=PaymentProvider.FLUTTERWAVE.value)
    provider_ref = Column(String(128), nullable=True, index=True)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default="NGN")
    status = Column(String(24), nullable=False, default=PaymentStatus.INITIATED.value, index=True)
    method = Column(String(16), nullable=False, default=PaymentMethod.CARD.value)
    wire_proof_url = Column(String(512), nullable=True)
    failure_reason = Column(String(512), nullable=True)
    confirmed_by_admin_id = Column(String(36), nullable=True)
    provider_metadata = Column(Text, nullable=True)


class PaymentAttempt(BaseEntity):
    __tablename__ = "payment_attempts"

    payment_id = Column(String(36), nullable=False, index=True)
    status = Column(String(24), nullable=False)
    provider_ref = Column(String(128), nullable=True)
    failure_reason = Column(String(512), nullable=True)
    event_payload = Column(Text, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────


class CreatePaymentDto(Object):
    verification_id: str
    provider: PaymentProvider = PaymentProvider.FLUTTERWAVE
    amount_minor: int
    currency: str = "NGN"
    status: PaymentStatus = PaymentStatus.INITIATED
    method: PaymentMethod = PaymentMethod.CARD
    provider_ref: Optional[str] = None


class UpdatePaymentDto(Object):
    status: Optional[PaymentStatus] = None
    provider_ref: Optional[str] = None
    wire_proof_url: Optional[str] = None
    failure_reason: Optional[str] = None
    confirmed_by_admin_id: Optional[str] = None
    provider_metadata: Optional[str] = None


class SearchPaymentDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None
    method: Optional[str] = None


class QueryPaymentDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None
    method: Optional[str] = None
    provider_ref: Optional[str] = None


class CreatePaymentAttemptDto(Object):
    payment_id: str
    status: PaymentStatus
    provider_ref: Optional[str] = None
    failure_reason: Optional[str] = None
    event_payload: Optional[str] = None


class UpdatePaymentAttemptDto(Object):
    pass


class SearchPaymentAttemptDto(PageRequest, BaseQueryDto):
    payment_id: Optional[str] = None


class QueryPaymentAttemptDto(BaseQueryDto):
    payment_id: Optional[str] = None


# ── Public DTOs ──


class InitiatePaymentDto(Object):
    verification_id: str
    method: PaymentMethod
    redirect_url: Optional[str] = None


class WireProofDto(Object):
    proof_url: str


class ConfirmWireDto(Object):
    note: Optional[str] = None


class PaymentDto(Object):
    id: str
    verification_id: str
    provider: PaymentProvider
    method: PaymentMethod
    status: PaymentStatus
    amount_minor: int
    currency: str
    provider_ref: Optional[str] = None
    failure_reason: Optional[str] = None
    wire_proof_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class InitiatePaymentResultDto(Object):
    payment: PaymentDto
    # For CARD method: redirect URL the frontend should open. For TRANSFER:
    # virtual account number + expiry. For WIRE: SWIFT/IBAN instructions.
    checkout_url: Optional[str] = None
    instructions: Optional[dict] = None
