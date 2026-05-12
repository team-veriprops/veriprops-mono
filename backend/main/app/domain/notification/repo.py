"""Notification repos — S39."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.notification.models import (
    Notification,
    NotificationDispatch,
    NotificationPreference,
    CreateNotificationDto,
    UpdateNotificationDto,
    SearchNotificationDto,
    QueryNotificationDto,
    CreateNotificationDispatchDto,
    UpdateNotificationDispatchDto,
    QueryNotificationDispatchDto,
    UpsertNotificationPreferenceDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class NotificationRepo(GenericRepo[
                           Notification,
                           CreateNotificationDto,
                           UpdateNotificationDto,
                           QueryNotificationDto,
                           SearchNotificationDto,
                       ]):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[Notification] = Notification,
            query_dto: Type[QueryNotificationDto] = QueryNotificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_recipient(self, recipient_id: str, limit: int = 30) -> List[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.recipient_id == recipient_id, Notification.deleted == False)
            .order_by(Notification.date_created.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_read(self, notification_id: str) -> None:
        row = await self._session.get(Notification, notification_id)
        if row:
            row.read = True


@inject
class NotificationDispatchRepo(GenericRepo[
                                   NotificationDispatch,
                                   CreateNotificationDispatchDto,
                                   UpdateNotificationDispatchDto,
                                   QueryNotificationDispatchDto,
                                   SearchNotificationDto,
                               ]):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[NotificationDispatch] = NotificationDispatch,
            query_dto: Type[QueryNotificationDispatchDto] = QueryNotificationDispatchDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db


@inject
class NotificationPreferenceRepo(GenericRepo[
                                     NotificationPreference,
                                     UpsertNotificationPreferenceDto,
                                     UpsertNotificationPreferenceDto,
                                     QueryNotificationDto,
                                     SearchNotificationDto,
                                 ]):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[NotificationPreference] = NotificationPreference,
            query_dto: Type[QueryNotificationDto] = QueryNotificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for_user_and_event(
            self, user_id: str, event_type: str
    ) -> Optional[NotificationPreference]:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
                NotificationPreference.deleted == False,
            )
        )
        return result.scalars().first()

    async def list_for_user(self, user_id: str) -> List[NotificationPreference]:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.deleted == False,
            )
        )
        return list(result.scalars().all())
