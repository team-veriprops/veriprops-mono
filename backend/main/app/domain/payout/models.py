"""Payout domain — S48."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Boolean, Column, Numeric, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class PayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    ON_HOLD = "ON_HOLD"


class BankAccount(BaseEntity):
    __tablename__ = "bank_accounts"

    agent_id = Column(String(36), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(20), nullable=False)
    account_holder_name = Column(String(200), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)


class Payout(BaseEntity):
    __tablename__ = "payouts"

    agent_id = Column(String(36), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    bank_account_id = Column(String(36), nullable=False)
    status = Column(String(16), nullable=False, default=PayoutStatus.PENDING.value)
    requested_at = Column(UTCDateTime, nullable=False)
    approved_at = Column(UTCDateTime, nullable=True)
    paid_at = Column(UTCDateTime, nullable=True)
    hold_reason = Column(Text, nullable=True)


class PayoutAdjustment(BaseEntity):
    __tablename__ = "payout_adjustments"

    payout_id = Column(String(36), nullable=False, index=True)
    adjusted_by = Column(String(36), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=False)
    new_amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=False)


# ── DTOs ──────────────────────────────────────────────────────────────────────


class BankAccountDto(Object):
    id: str
    agent_id: str
    bank_name: str
    account_number: str
    account_holder_name: str
    is_default: bool
    date_created: str


class CreateBankAccountDto(Object):
    agent_id: str
    bank_name: str
    account_number: str
    account_holder_name: str
    is_default: bool = False


class UpdateBankAccountDto(Object):
    is_default: Optional[bool] = None


class QueryBankAccountDto(BaseQueryDto):
    agent_id: Optional[str] = None


class SearchBankAccountDto(PageRequest, BaseQueryDto):
    agent_id: Optional[str] = None


class PayoutDto(Object):
    id: str
    agent_id: str
    amount: float
    bank_account_id: str
    status: PayoutStatus
    requested_at: str
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    hold_reason: Optional[str] = None
    date_created: str


class CreatePayoutDto(Object):
    agent_id: str
    amount: float
    bank_account_id: str
    status: str = PayoutStatus.PENDING.value
    requested_at: str


class UpdatePayoutDto(Object):
    status: Optional[str] = None
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    hold_reason: Optional[str] = None
    amount: Optional[float] = None


class QueryPayoutDto(BaseQueryDto):
    agent_id: Optional[str] = None
    status: Optional[str] = None


class SearchPayoutDto(PageRequest, BaseQueryDto):
    agent_id: Optional[str] = None
    status: Optional[str] = None


class CreatePayoutAdjustmentDto(Object):
    payout_id: str
    adjusted_by: str
    original_amount: float
    new_amount: float
    reason: str


class WithdrawalRequestDto(Object):
    amount: float
    bank_account_id: str


class HoldPayoutDto(Object):
    reason: str


class AdjustPayoutDto(Object):
    new_amount: float
    reason: str
