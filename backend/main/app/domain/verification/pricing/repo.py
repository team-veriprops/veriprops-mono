"""Pricing repos — S54."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.pricing.models import (
    CreatePricingLineItemDto,
    CreatePricingTierConfigDto,
    CreatePricingUpgradeDeltaDto,
    PricingLineItem,
    PricingTierConfig,
    PricingUpgradeDelta,
    QueryPricingLineItemDto,
    QueryPricingTierConfigDto,
    QueryPricingUpgradeDeltaDto,
    SearchPricingLineItemDto,
    SearchPricingTierConfigDto,
    SearchPricingUpgradeDeltaDto,
    UpdatePricingLineItemDto,
    UpdatePricingTierConfigDto,
    UpdatePricingUpgradeDeltaDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


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

    async def get_active_for_tier(self, tier: str, currency: str = "NGN") -> Optional[PricingTierConfig]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingTierConfig).where(
                PricingTierConfig.tier == tier,
                PricingTierConfig.currency == currency,
                PricingTierConfig.is_active == True,
                PricingTierConfig.deleted == False,
            ).limit(1)
        )
        return result.scalars().first()

    async def list_all_active(self) -> List[PricingTierConfig]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingTierConfig).where(
                PricingTierConfig.is_active == True,
                PricingTierConfig.deleted == False,
            ).order_by(PricingTierConfig.tier)
        )
        return list(result.scalars().all())

    async def get_for_tier_currency(self, tier: str, currency: str) -> Optional[PricingTierConfig]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingTierConfig).where(
                PricingTierConfig.tier == tier,
                PricingTierConfig.currency == currency,
                PricingTierConfig.deleted == False,
            ).limit(1)
        )
        return result.scalars().first()


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

    async def list_for_config(self, tier_config_id: str) -> List[PricingLineItem]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingLineItem).where(
                PricingLineItem.tier_config_id == tier_config_id,
                PricingLineItem.deleted == False,
            ).order_by(PricingLineItem.sort_order)
        )
        return list(result.scalars().all())

    async def delete_for_config(self, tier_config_id: str) -> None:
        from main.appodus_utils import Utils
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingLineItem).where(
                PricingLineItem.tier_config_id == tier_config_id,
                PricingLineItem.deleted == False,
            )
        )
        for row in result.scalars().all():
            row.deleted = True
            row.date_updated = Utils.datetime_now()


@inject
class PricingUpgradeDeltaRepo(
    GenericRepo[
        PricingUpgradeDelta,
        CreatePricingUpgradeDeltaDto,
        UpdatePricingUpgradeDeltaDto,
        QueryPricingUpgradeDeltaDto,
        SearchPricingUpgradeDeltaDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[PricingUpgradeDelta] = PricingUpgradeDelta,
        query_dto: Type[QueryPricingUpgradeDeltaDto] = QueryPricingUpgradeDeltaDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_for_pair(self, from_tier: str, to_tier: str, currency: str = "NGN") -> Optional[PricingUpgradeDelta]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingUpgradeDelta).where(
                PricingUpgradeDelta.from_tier == from_tier,
                PricingUpgradeDelta.to_tier == to_tier,
                PricingUpgradeDelta.currency == currency,
                PricingUpgradeDelta.deleted == False,
            ).limit(1)
        )
        return result.scalars().first()

    async def list_all(self) -> List[PricingUpgradeDelta]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(PricingUpgradeDelta).where(
                PricingUpgradeDelta.deleted == False,
            ).order_by(PricingUpgradeDelta.from_tier)
        )
        return list(result.scalars().all())
