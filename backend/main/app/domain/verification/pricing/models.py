"""DB-backed pricing models — S54 Phase 18.

Replaces the static TIER_MATRIX with admin-editable DB rows. The legacy
PricingService.quote() method is preserved for backward compat.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, Object


# ─── ORM ──────────────────────────────────────────────────────────


class PricingTierConfig(BaseEntity):
    __tablename__ = "pricing_tier_configs"

    tier = Column(String(16), nullable=False, index=True)
    label = Column(String(128), nullable=False)
    currency = Column(String(8), nullable=False, default="NGN")
    service_fee_minor = Column(BigInteger, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_by = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("tier", "currency", name="uq_pricing_tier_currency"),
    )


class PricingLineItem(BaseEntity):
    __tablename__ = "pricing_line_items"

    tier_config_id = Column(String(36), nullable=False, index=True)
    label = Column(String(128), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    description = Column(String(512), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class PricingUpgradeDelta(BaseEntity):
    __tablename__ = "pricing_upgrade_deltas"

    from_tier = Column(String(16), nullable=False)
    to_tier = Column(String(16), nullable=False)
    delta_minor = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default="NGN")
    updated_by = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("from_tier", "to_tier", "currency", name="uq_pricing_upgrade_delta"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────


class PricingLineItemDto(Object):
    id: Optional[str] = None
    label: str
    amount_minor: int
    description: Optional[str] = None
    sort_order: int = 0


class PricingTierConfigDto(Object):
    id: str
    tier: str
    label: str
    currency: str
    service_fee_minor: int
    is_active: bool
    line_items: List[PricingLineItemDto] = []
    updated_by: Optional[str] = None
    date_updated: Optional[datetime] = None


class CreatePricingTierConfigDto(Object):
    tier: str
    label: str
    currency: str = "NGN"
    service_fee_minor: int
    is_active: bool = True
    updated_by: Optional[str] = None


class UpdatePricingTierConfigDto(Object):
    label: Optional[str] = None
    service_fee_minor: Optional[int] = None
    is_active: Optional[bool] = None
    updated_by: Optional[str] = None


class QueryPricingTierConfigDto(Object):
    tier: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


class SearchPricingTierConfigDto(QueryPricingTierConfigDto):
    pass


class CreatePricingLineItemDto(Object):
    tier_config_id: str
    label: str
    amount_minor: int
    description: Optional[str] = None
    sort_order: int = 0


class UpdatePricingLineItemDto(Object):
    label: Optional[str] = None
    amount_minor: Optional[int] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class QueryPricingLineItemDto(Object):
    tier_config_id: Optional[str] = None


class SearchPricingLineItemDto(QueryPricingLineItemDto):
    pass


class PricingUpgradeDeltaDto(Object):
    id: str
    from_tier: str
    to_tier: str
    delta_minor: int
    currency: str
    updated_by: Optional[str] = None
    date_updated: Optional[datetime] = None


class CreatePricingUpgradeDeltaDto(Object):
    from_tier: str
    to_tier: str
    delta_minor: int
    currency: str = "NGN"
    updated_by: Optional[str] = None


class UpdatePricingUpgradeDeltaDto(Object):
    delta_minor: Optional[int] = None
    updated_by: Optional[str] = None


class QueryPricingUpgradeDeltaDto(Object):
    from_tier: Optional[str] = None
    to_tier: Optional[str] = None
    currency: Optional[str] = None


class SearchPricingUpgradeDeltaDto(QueryPricingUpgradeDeltaDto):
    pass


# ── Upsert inputs from admin UI ──


class UpsertPricingLineItemPayload(Object):
    label: str
    amount_minor: int
    description: Optional[str] = None
    sort_order: int = 0


class UpsertPricingTierDto(Object):
    tier: str
    label: str
    currency: str = "NGN"
    service_fee_minor: int
    line_items: List[UpsertPricingLineItemPayload] = []


class UpsertUpgradeDeltaDto(Object):
    from_tier: str
    to_tier: str
    delta_minor: int
    currency: str = "NGN"
