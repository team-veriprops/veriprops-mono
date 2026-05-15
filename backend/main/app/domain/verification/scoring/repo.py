"""Repositories for trust score weight config and breakdowns."""
from __future__ import annotations

from typing import List, Optional

from kink import inject
from sqlalchemy import select

from main.app.domain.verification.scoring.models import (
    CreateBreakdownDto,
    CreateWeightConfigDto,
    TrustScoreBreakdown,
    TrustScoreWeightConfig,
    UpdateWeightDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class TrustScoreWeightRepo(
    GenericRepo[TrustScoreWeightConfig, CreateWeightConfigDto, UpdateWeightDto, None, None]
):
    def __init__(self) -> None:
        super().__init__(TrustScoreWeightConfig)

    async def list_for_tier(self, tier: str) -> List[TrustScoreWeightConfig]:
        session = self._session
        result = await session.execute(
            select(TrustScoreWeightConfig)
            .where(
                TrustScoreWeightConfig.tier == tier,
                TrustScoreWeightConfig.deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    async def list_all(self) -> List[TrustScoreWeightConfig]:
        session = self._session
        result = await session.execute(
            select(TrustScoreWeightConfig)
            .where(TrustScoreWeightConfig.deleted.is_(False))
            .order_by(TrustScoreWeightConfig.tier, TrustScoreWeightConfig.role)
        )
        return list(result.scalars().all())

    async def get_for_tier_role(self, tier: str, role: str) -> Optional[TrustScoreWeightConfig]:
        session = self._session
        result = await session.execute(
            select(TrustScoreWeightConfig)
            .where(
                TrustScoreWeightConfig.tier == tier,
                TrustScoreWeightConfig.role == role,
                TrustScoreWeightConfig.deleted.is_(False),
            )
        )
        return result.scalars().first()


@inject
class TrustScoreBreakdownRepo(
    GenericRepo[TrustScoreBreakdown, CreateBreakdownDto, None, None, None]
):
    def __init__(self) -> None:
        super().__init__(TrustScoreBreakdown)

    async def latest_for_verification(self, verification_id: str) -> Optional[TrustScoreBreakdown]:
        session = self._session
        result = await session.execute(
            select(TrustScoreBreakdown)
            .where(
                TrustScoreBreakdown.verification_id == verification_id,
                TrustScoreBreakdown.deleted.is_(False),
            )
            .order_by(TrustScoreBreakdown.computed_at.desc())
            .limit(1)
        )
        return result.scalars().first()
