"""Referral link data access."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.referral.models import (
    CreateReferralDto,
    QueryReferralDto,
    Referral,
    SearchReferralDto,
    UpdateReferralDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ReferralRepo(
    GenericRepo[Referral, CreateReferralDto, UpdateReferralDto, QueryReferralDto, SearchReferralDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Referral] = Referral,
        query_dto: Type[QueryReferralDto] = QueryReferralDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for_referrer(self, referrer_user_id: str) -> Optional[Referral]:
        stmt = select(Referral).where(
            Referral.deleted.is_(False),
            Referral.referrer_user_id == referrer_user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Referral]:
        stmt = select(Referral).where(
            Referral.deleted.is_(False),
            Referral.code == code,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
