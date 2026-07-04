"""Commission domain (PRD §15.2 — introduced early per decision-log D13).

A commission is money owed to an agent for an approved task, held in **clearing**
until a chargeback window passes, then **available**. Modelled in integer minor
units, NGN-contractual (§4.4). This slice (S10) builds the entity + the freeze /
unfreeze / reverse operations the chargeback sub-process (§6a) needs; accrual is
wired at task approval / report release in S12, and the earnings/payout surface is
built out in S19 (Phase 15) on top of this base.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Index, String

from main.app.core.state.status import AgentRole, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.db.types.money import TransactionCurrency


class CommissionStatus(str, enum.Enum):
    """Lifecycle of an agent commission (PRD §15.2)."""

    CLEARING = "CLEARING"    # accrued; held through the chargeback window
    AVAILABLE = "AVAILABLE"  # cleared; withdrawable
    FROZEN = "FROZEN"        # chargeback in progress — clearing paused (§6a.2)
    REVERSED = "REVERSED"    # chargeback lost — clawed back


# ─── ORM ──────────────────────────────────────────────────────────

class Commission(BaseEntity):
    __tablename__ = "commissions"

    verification_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    agent_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    tier = Column(String(16), nullable=False)

    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default=TransactionCurrency.NGN.value)
    status = Column(String(16), nullable=False, default=CommissionStatus.CLEARING.value, index=True)
    # When a CLEARING commission becomes AVAILABLE (past the chargeback window).
    clearing_until = Column(UTCDateTime, nullable=True)
    # Prior status captured on freeze so an un-freeze restores it exactly (§6a.2).
    frozen_from_status = Column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_commissions_verification", "verification_id"),
        Index("ix_commissions_agent", "agent_id"),
        Index("ix_commissions_status", "status"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateCommissionDto(Object):
    verification_id: str
    task_id: Optional[str] = None
    agent_id: str
    role: AgentRole
    tier: VerificationTier
    amount_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN
    status: CommissionStatus = CommissionStatus.CLEARING


class UpdateCommissionDto(Object):
    status: Optional[str] = None
    frozen_from_status: Optional[str] = None


class SearchCommissionDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = None


class QueryCommissionDto(BaseQueryDto):
    verification_id: Optional[str] = None
    agent_id: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class CommissionDto(Object):
    id: str
    verification_id: str
    task_id: Optional[str] = None
    agent_id: str
    role: AgentRole
    tier: VerificationTier
    amount_minor: int
    currency: TransactionCurrency
    status: CommissionStatus
    clearing_until: Optional[datetime] = None
    date_created: datetime
