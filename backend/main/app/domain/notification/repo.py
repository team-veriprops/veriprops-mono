"""Notification data access — the per-user feed, unread counter, and mark-read."""
from __future__ import annotations

from typing import List, Tuple, Type

from kink import inject
from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.notification.models import (
    CreateNotificationDto,
    Notification,
    QueryNotificationDto,
    SearchNotificationDto,
    UpdateNotificationDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class NotificationRepo(
    GenericRepo[
        Notification,
        CreateNotificationDto,
        UpdateNotificationDto,
        QueryNotificationDto,
        SearchNotificationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Notification] = Notification,
        query_dto: Type[QueryNotificationDto] = QueryNotificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(
        self, user_id: str, page: int, page_size: int
    ) -> Tuple[List[Notification], int]:
        """Returns ``(rows, total)`` — the service builds the typed page from DTOs so ORM
        models never reach ``build_page``."""
        offset = page * page_size
        where = and_(Notification.deleted.is_(False), Notification.user_id == str(user_id))
        total = int((await self._session.execute(
            select(func.count(Notification.id)).where(where)
        )).scalar() or 0)
        stmt = (
            select(Notification)
            .where(where)
            .order_by(desc(Notification.date_created))
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def unread_count(self, user_id: str) -> int:
        where = and_(
            Notification.deleted.is_(False),
            Notification.user_id == user_id,
            Notification.read.is_(False),
        )
        return int((await self._session.execute(
            select(func.count(Notification.id)).where(where)
        )).scalar() or 0)

    async def mark_all_read(self, user_id: str) -> int:
        stmt = (
            update(Notification)
            .where(
                and_(
                    Notification.deleted.is_(False),
                    Notification.user_id == user_id,
                    Notification.read.is_(False),
                )
            )
            .values(read=True)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0
