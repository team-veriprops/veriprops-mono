"""Broadcast data access."""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.broadcast.models import (
    Broadcast,
    BroadcastStatus,
    CreateBroadcastDto,
    QueryBroadcastDto,
    SearchBroadcastDto,
    UpdateBroadcastDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class BroadcastRepo(
    GenericRepo[Broadcast, CreateBroadcastDto, UpdateBroadcastDto, QueryBroadcastDto, SearchBroadcastDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Broadcast] = Broadcast,
        query_dto: Type[QueryBroadcastDto] = QueryBroadcastDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_due_scheduled(self, now: datetime) -> List[Broadcast]:
        """SCHEDULED broadcasts whose send time has passed (§18.1 sweep)."""
        stmt = select(Broadcast).where(
            Broadcast.deleted.is_(False),
            Broadcast.status == BroadcastStatus.SCHEDULED.value,
            Broadcast.scheduled_at.is_not(None),
            Broadcast.scheduled_at <= now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_all(self, page: int, page_size: int, status: str | None = None) -> Tuple[List[Broadcast], int]:
        conditions = [Broadcast.deleted.is_(False)]
        if status:
            conditions.append(Broadcast.status == status)
        base = select(Broadcast).where(*conditions)
        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = base.order_by(Broadcast.date_created.desc()).offset(page * page_size).limit(page_size)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total
