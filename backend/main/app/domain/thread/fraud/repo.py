"""Fraud flag repository (S38 / S57)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, select
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

    async def list_all(
        self,
        reviewed: Optional[bool],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        offset: int,
        limit: int,
    ) -> Tuple[List[FraudFlag], int]:
        base = select(FraudFlag).where(FraudFlag.deleted.is_(False))
        if reviewed is not None:
            base = base.where(FraudFlag.reviewed.is_(reviewed))
        if date_from:
            base = base.where(FraudFlag.date_created >= date_from)
        if date_to:
            base = base.where(FraudFlag.date_created <= date_to)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(FraudFlag.date_created.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0
