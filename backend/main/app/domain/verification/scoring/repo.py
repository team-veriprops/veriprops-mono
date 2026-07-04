"""Trust Score Weights data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.scoring.models import (
    CreateTrustWeightDto,
    QueryTrustWeightDto,
    SearchTrustWeightDto,
    TrustScoreWeight,
    UpdateTrustWeightDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class TrustScoreWeightRepo(
    GenericRepo[
        TrustScoreWeight,
        CreateTrustWeightDto,
        UpdateTrustWeightDto,
        QueryTrustWeightDto,
        SearchTrustWeightDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[TrustScoreWeight] = TrustScoreWeight,
        query_dto: Type[QueryTrustWeightDto] = QueryTrustWeightDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_all(self) -> List[TrustScoreWeight]:
        stmt = select(TrustScoreWeight).where(TrustScoreWeight.deleted.is_(False))
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_tier(self, tier: str) -> List[TrustScoreWeight]:
        stmt = select(TrustScoreWeight).where(
            TrustScoreWeight.deleted.is_(False), TrustScoreWeight.tier == tier
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_for_tier_role(self, tier: str, role: str) -> Optional[TrustScoreWeight]:
        stmt = select(TrustScoreWeight).where(
            TrustScoreWeight.deleted.is_(False),
            TrustScoreWeight.tier == tier,
            TrustScoreWeight.role == role,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
