"""Broadcast repo — S55."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.broadcast.models import (
    Broadcast,
    BroadcastStatus,
    CreateBroadcastDto,
    QueryBroadcastDto,
    SearchBroadcastDto,
    UpdateBroadcastDto, BroadcastAudience,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class BroadcastRepo(
    GenericRepo[
        Broadcast,
        CreateBroadcastDto,
        UpdateBroadcastDto,
        QueryBroadcastDto,
        SearchBroadcastDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Broadcast] = Broadcast,
        query_dto: Type[QueryBroadcastDto] = QueryBroadcastDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_due_scheduled(self) -> List[Broadcast]:
        from main.appodus_utils import Utils
        session = self._session
        now = Utils.datetime_now()
        result = await session.execute(
            select(Broadcast).where(
                Broadcast.status == BroadcastStatus.SCHEDULED.value,
                Broadcast.scheduled_at <= now,
                Broadcast.deleted == False,
            )
        )
        return list(result.scalars().all())

    async def list_all(self, page: int = 0, page_size: int = 25):
        from sqlalchemy import func
        session = self._session
        filters = [Broadcast.deleted == False]
        total = await session.scalar(select(func.count(Broadcast.id)).where(*filters)) or 0
        result = await session.execute(
            select(Broadcast).where(*filters).order_by(Broadcast.date_created.desc())
            .offset(page * page_size).limit(page_size)
        )
        return list(result.scalars().all()), int(total)

    async def get_broadcast_user_ids(self, audience: BroadcastAudience) -> list[str]:
        from main.app.domain.user.models import User
        from main.app.domain.user.auth.session.models import UserType, UserPersona

        stmt = select(User.id).where(User.deleted == False)
        if audience == BroadcastAudience.ADMINS:
            stmt = stmt.where(User.user_type == UserType.ADMIN.value)
        elif audience == BroadcastAudience.CUSTOMERS:
            stmt = stmt.where(User.personas.in_(UserPersona.CUSTOMER.value))
        elif audience == BroadcastAudience.AGENTS:
            stmt = stmt.where(User.personas.in_(UserPersona.AGENT.value))
        result = await self._session.execute(stmt)

        return [str(r) for r in result.scalars().all()]
