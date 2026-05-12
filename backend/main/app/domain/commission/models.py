"""Commission domain — S47."""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Column, Date, Numeric, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class EarningStatus(str, enum.Enum):
    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    PAID = "PAID"


class CommissionRule(BaseEntity):
    __tablename__ = "commission_rules"

    role = Column(String(20), nullable=False)
    tier = Column(String(16), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    effective_date = Column(Date, nullable=False)


class Earning(BaseEntity):
    __tablename__ = "earnings"

    agent_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(36), nullable=False, index=True)
    verification_id = Column(String(36), nullable=False)
    gross_amount = Column(Numeric(12, 2), nullable=False)
    commission_pct = Column(Numeric(5, 2), nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(16), nullable=False, default=EarningStatus.PENDING.value)
    computed_at = Column(UTCDateTime, nullable=False)


class CommissionRuleDto(Object):
    id: str
    role: str
    tier: str
    percentage: float
    effective_date: str
    date_created: str


class CreateCommissionRuleDto(Object):
    role: str
    tier: str
    percentage: float
    effective_date: str


class UpdateCommissionRuleDto(Object):
    percentage: Optional[float] = None
    effective_date: Optional[str] = None


class QueryCommissionRuleDto(BaseQueryDto):
    role: Optional[str] = None
    tier: Optional[str] = None


class SearchCommissionRuleDto(PageRequest, BaseQueryDto):
    role: Optional[str] = None
    tier: Optional[str] = None


class EarningDto(Object):
    id: str
    agent_id: str
    task_id: str
    verification_id: str
    gross_amount: float
    commission_pct: float
    net_amount: float
    status: EarningStatus
    computed_at: str
    date_created: str


class CreateEarningDto(Object):
    agent_id: str
    task_id: str
    verification_id: str
    gross_amount: float
    commission_pct: float
    net_amount: float
    status: str = EarningStatus.PENDING.value
    computed_at: str


class UpdateEarningDto(Object):
    status: Optional[str] = None


class QueryEarningDto(BaseQueryDto):
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    status: Optional[str] = None


class SearchEarningDto(PageRequest, BaseQueryDto):
    agent_id: Optional[str] = None
    status: Optional[str] = None


class EarningsSummaryDto(Object):
    total_lifetime: float
    total_pending: float
    total_available: float
    total_paid: float


class CommissionPreviewDto(Object):
    role: str
    tier: str
    percentage: float
    estimated_net: float
