"""Notification preference data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.notification_preference.models import (
    CreateNotificationPreferenceDto,
    NotificationPreference,
    QueryNotificationPreferenceDto,
    SearchNotificationPreferenceDto,
    UpdateNotificationPreferenceDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class NotificationPreferenceRepo(
    GenericRepo[
        NotificationPreference,
        CreateNotificationPreferenceDto,
        UpdateNotificationPreferenceDto,
        QueryNotificationPreferenceDto,
        SearchNotificationPreferenceDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[NotificationPreference] = NotificationPreference,
        query_dto: Type[QueryNotificationPreferenceDto] = QueryNotificationPreferenceDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[NotificationPreference]:
        stmt = select(NotificationPreference).where(
            and_(
                NotificationPreference.deleted.is_(False),
                NotificationPreference.user_id == user_id,
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_one(self, user_id: str, event_type: str) -> Optional[NotificationPreference]:
        stmt = select(NotificationPreference).where(
            and_(
                NotificationPreference.deleted.is_(False),
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()
