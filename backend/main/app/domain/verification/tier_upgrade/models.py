"""Tier upgrade domain — S45."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Column, Numeric, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class TierUpgradeStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class TierUpgrade(BaseEntity):
    __tablename__ = "tier_upgrades"

    verification_id = Column(String(36), nullable=False, index=True)
    from_tier = Column(String(16), nullable=False)
    to_tier = Column(String(16), nullable=False)
    delta_price = Column(Numeric(12, 2), nullable=True)
    status = Column(String(16), nullable=False, default=TierUpgradeStatus.PENDING.value)
    requested_by = Column(String(36), nullable=False)
    payment_id = Column(String(36), nullable=True)


class TierUpgradeDto(Object):
    id: str
    verification_id: str
    from_tier: str
    to_tier: str
    delta_price: Optional[float] = None
    status: TierUpgradeStatus
    requested_by: str
    payment_id: Optional[str] = None
    date_created: str


class CreateTierUpgradeDto(Object):
    verification_id: str
    from_tier: str
    to_tier: str
    delta_price: Optional[float] = None
    status: str = TierUpgradeStatus.PENDING.value
    requested_by: str


class UpdateTierUpgradeDto(Object):
    status: Optional[str] = None
    payment_id: Optional[str] = None


class QueryTierUpgradeDto(BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SearchTierUpgradeDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class SubmitTierUpgradeDto(Object):
    to_tier: str


class TierUpgradePreviewDto(Object):
    from_tier: str
    to_tier: str
    delta_price: float
