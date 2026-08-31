"""Handoff redemption data access."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.handoff.models import (
    CreateHandoffTokenRedemptionDto,
    HandoffTokenRedemption,
    QueryHandoffTokenRedemptionDto,
    SearchHandoffTokenRedemptionDto,
    UpdateHandoffTokenRedemptionDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class HandoffTokenRedemptionRepo(
    GenericRepo[
        HandoffTokenRedemption,
        CreateHandoffTokenRedemptionDto,
        UpdateHandoffTokenRedemptionDto,
        QueryHandoffTokenRedemptionDto,
        SearchHandoffTokenRedemptionDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[HandoffTokenRedemption] = HandoffTokenRedemption,
        query_dto: Type[QueryHandoffTokenRedemptionDto] = QueryHandoffTokenRedemptionDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_jti(self, jti: str) -> Optional[HandoffTokenRedemption]:
        """Whether this nonce has already been spent.

        Soft-deleted rows count: a redemption that was later tidied away still means the
        link was used once, and a replay must not resurrect it.
        """
        stmt = select(HandoffTokenRedemption).where(HandoffTokenRedemption.jti == jti)
        return (await self._session.execute(stmt)).scalars().first()
