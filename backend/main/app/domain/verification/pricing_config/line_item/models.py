"""Pricing line item (PRD §5.2, §18.1) — an itemized breakdown row for a tier.

Line items are the customer-facing itemization of a tier's price (§5.2). The tier's
``price_ngn_kobo`` remains the authoritative charged amount; line items are display
detail, editable by admins (Pricing config, §18.1).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


class PricingLineItem(BaseEntity):
    __tablename__ = "pricing_line_items"

    tier = Column(String(16), nullable=False, index=True)
    label = Column(String(128), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    sort_order = Column(Integer, nullable=False, server_default="0")
    # tier index is declared inline (index=True) → ix_pricing_line_items_tier, matching the migration.


# ─── DTOs ─────────────────────────────────────────────────────────

class CreatePricingLineItemDto(Object):
    tier: str
    label: str
    amount_minor: int
    sort_order: int = 0


class UpdatePricingLineItemDto(Object):
    label: Optional[str] = None
    amount_minor: Optional[int] = None
    sort_order: Optional[int] = None


class QueryPricingLineItemDto(BaseQueryDto):
    tier: Optional[str] = None


class SearchPricingLineItemDto(InternalPageRequest, BaseQueryDto):
    tier: Optional[str] = None


class PricingLineItemDto(Object):
    id: str
    tier: str
    label: str
    amount_minor: int
    sort_order: int = 0
    date_created: datetime
