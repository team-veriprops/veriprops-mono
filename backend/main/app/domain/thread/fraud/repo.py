"""Fraud flag repository (S38)."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.thread.fraud.models import (
    CreateFraudFlagDto,
    FraudFlag,
    QueryFraudFlagDto,
    SearchFraudFlagDto,
    UpdateFraudFlagDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class FraudFlagRepo(
    GenericRepo[
        FraudFlag,
        CreateFraudFlagDto,
        UpdateFraudFlagDto,
        QueryFraudFlagDto,
        SearchFraudFlagDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[FraudFlag] = FraudFlag,
        query_dto: Type[QueryFraudFlagDto] = QueryFraudFlagDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_pending(self) -> List[FraudFlag]:
        stmt = (
            select(FraudFlag)
            .where(FraudFlag.deleted.is_(False), FraudFlag.reviewed.is_(False))
            .order_by(FraudFlag.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
