"""Pricing line item data access."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.pricing_config.line_item.models import (
    CreatePricingLineItemDto,
    PricingLineItem,
    QueryPricingLineItemDto,
    SearchPricingLineItemDto,
    UpdatePricingLineItemDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PricingLineItemRepo(
    GenericRepo[
        PricingLineItem,
        CreatePricingLineItemDto,
        UpdatePricingLineItemDto,
        QueryPricingLineItemDto,
        SearchPricingLineItemDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[PricingLineItem] = PricingLineItem,
        query_dto: Type[QueryPricingLineItemDto] = QueryPricingLineItemDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_all(self) -> List[PricingLineItem]:
        stmt = select(PricingLineItem).where(PricingLineItem.deleted.is_(False)).order_by(
            PricingLineItem.tier, PricingLineItem.sort_order
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_tier(self, tier: str) -> List[PricingLineItem]:
        stmt = select(PricingLineItem).where(
            PricingLineItem.deleted.is_(False),
            PricingLineItem.tier == tier,
        ).order_by(PricingLineItem.sort_order)
        return list((await self._session.execute(stmt)).scalars().all())
