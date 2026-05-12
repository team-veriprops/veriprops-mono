"""Referral domain repos."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.referral.models import (
    CreateReferralCodeDto,
    CreateReferralRedemptionDto,
    QueryReferralCodeDto,
    QueryReferralRedemptionDto,
    ReferralCode,
    ReferralRedemption,
    RedemptionStatus,
    SearchReferralCodeDto,
    SearchReferralRedemptionDto,
    UpdateReferralCodeDto,
    UpdateReferralRedemptionDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ReferralCodeRepo(
    GenericRepo[
        ReferralCode,
        CreateReferralCodeDto,
        UpdateReferralCodeDto,
        QueryReferralCodeDto,
        SearchReferralCodeDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReferralCode] = ReferralCode,
        query_dto: Type[QueryReferralCodeDto] = QueryReferralCodeDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_by_owner(self, owner_id: str) -> Optional[ReferralCode]:
        stmt = (
            select(ReferralCode)
            .where(
                ReferralCode.deleted.is_(False),
                ReferralCode.owner_id == owner_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[ReferralCode]:
        stmt = (
            select(ReferralCode)
            .where(
                ReferralCode.deleted.is_(False),
                ReferralCode.code == code.upper(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


@inject
class ReferralRedemptionRepo(
    GenericRepo[
        ReferralRedemption,
        CreateReferralRedemptionDto,
        UpdateReferralRedemptionDto,
        QueryReferralRedemptionDto,
        SearchReferralRedemptionDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReferralRedemption] = ReferralRedemption,
        query_dto: Type[QueryReferralRedemptionDto] = QueryReferralRedemptionDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_by_invitee(self, invitee_id: str) -> Optional[ReferralRedemption]:
        stmt = (
            select(ReferralRedemption)
            .where(
                ReferralRedemption.deleted.is_(False),
                ReferralRedemption.invitee_id == invitee_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_code(self, referral_code_id: str) -> List[ReferralRedemption]:
        stmt = (
            select(ReferralRedemption)
            .where(
                ReferralRedemption.deleted.is_(False),
                ReferralRedemption.referral_code_id == referral_code_id,
            )
            .order_by(ReferralRedemption.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
