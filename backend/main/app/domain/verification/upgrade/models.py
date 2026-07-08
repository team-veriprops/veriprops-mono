"""Tier-upgrade domain (PRD §14.2)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Index, String

from main.app.core.state.status import VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


class UpgradeStatus(str, enum.Enum):
    """Upgrade request lifecycle: PENDING (awaiting the delta payment) → PAID (applied). A
    superseded/abandoned request may be CANCELLED."""

    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


# ─── ORM ──────────────────────────────────────────────────────────

class UpgradeRequest(BaseEntity):
    __tablename__ = "upgrade_requests"

    verification_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    from_tier = Column(String(16), nullable=False)
    to_tier = Column(String(16), nullable=False)
    delta_minor = Column(BigInteger, nullable=False, default=0)
    status = Column(String(16), nullable=False, default=UpgradeStatus.PENDING.value, index=True)
    payment_id = Column(String(36), nullable=True, index=True)
    # Idempotency guard for resubmit (§14.2): {verification_id}:{to_tier}.
    idempotency_key = Column(String(80), nullable=False, unique=True, index=True)

    __table_args__ = (
        Index("ix_upgrade_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateUpgradeDto(Object):
    verification_id: str
    customer_id: str
    from_tier: VerificationTier
    to_tier: VerificationTier
    delta_minor: int
    idempotency_key: str
    status: UpgradeStatus = UpgradeStatus.PENDING


class UpdateUpgradeDto(Object):
    status: Optional[str] = None
    payment_id: Optional[str] = None


class QueryUpgradeDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchUpgradeDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None


class RequestUpgradeDto(Object):
    to_tier: VerificationTier


class UpgradeDto(Object):
    id: str
    verification_id: str
    from_tier: VerificationTier
    to_tier: VerificationTier
    delta_minor: int
    status: UpgradeStatus
    payment_id: Optional[str] = None
    checkout_url: Optional[str] = None
    date_created: datetime
