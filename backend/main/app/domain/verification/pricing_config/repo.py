"""Pricing tier config data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.pricing_config.models import (
    CreatePricingTierConfigDto,
    PricingTierConfig,
    QueryPricingTierConfigDto,
    SearchPricingTierConfigDto,
    UpdatePricingTierConfigDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PricingTierConfigRepo(
    GenericRepo[
        PricingTierConfig,
        CreatePricingTierConfigDto,
        UpdatePricingTierConfigDto,
        QueryPricingTierConfigDto,
        SearchPricingTierConfigDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[PricingTierConfig] = PricingTierConfig,
        query_dto: Type[QueryPricingTierConfigDto] = QueryPricingTierConfigDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for_tier(self, tier: str) -> Optional[PricingTierConfig]:
        stmt = select(PricingTierConfig).where(
            PricingTierConfig.deleted.is_(False),
            PricingTierConfig.tier == tier,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> List[PricingTierConfig]:
        stmt = select(PricingTierConfig).where(PricingTierConfig.deleted.is_(False))
        return list((await self._session.execute(stmt)).scalars().all())
