"""Pricing tier config (PRD §18.1, D36) — the admin-editable per-tier price.

Replaces the hardcoded ``TIER_PRICE_NGN_KOBO`` dict as the source of truth for the
contractual NGN price of each tier. Edits take effect on the **next quote** — existing
24h price locks are honoured (the locked amount lives on the verification row).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Column, String

from main.app.core.state.status import VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest

from main.app.domain.verification.pricing_config.line_item.models import PricingLineItemDto


class PricingTierConfig(BaseEntity):
    __tablename__ = "pricing_tier_config"

    tier = Column(String(16), nullable=False, unique=True, index=True)
    price_ngn_kobo = Column(BigInteger, nullable=False)
    # tier index is declared inline (unique=True, index=True) → ix_pricing_tier_config_tier, matching the migration.


# ─── DTOs ─────────────────────────────────────────────────────────

class CreatePricingTierConfigDto(Object):
    tier: str
    price_ngn_kobo: int


class UpdatePricingTierConfigDto(Object):
    price_ngn_kobo: Optional[int] = None


class QueryPricingTierConfigDto(BaseQueryDto):
    tier: Optional[str] = None


class SearchPricingTierConfigDto(InternalPageRequest, BaseQueryDto):
    tier: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class PricingTierDto(Object):
    """A tier's admin-editable price + its itemized breakdown (§18.1)."""

    tier: VerificationTier
    price_ngn_minor: int
    line_items: List[PricingLineItemDto] = []


class SetTierPriceDto(Object):
    price_ngn_minor: int


class LineItemInputDto(Object):
    label: str
    amount_minor: int


class SetLineItemsDto(Object):
    line_items: List[LineItemInputDto] = []


class UpgradeDeltaDto(Object):
    """A tier-upgrade charge (§14.2) shown in the pricing admin — target minus current."""

    from_tier: VerificationTier
    to_tier: VerificationTier
    delta_minor: int


class TierPricingViewDto(Object):
    tiers: List[PricingTierDto] = []
    upgrade_deltas: List[UpgradeDeltaDto] = []
