"""Notification repos — S39."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from kink import inject

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
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class NotificationRepo(GenericRepo[
    Notification,
    CreateNotificationDto,
    UpdateNotificationDto,
    QueryNotificationDto,
    SearchNotificationDto,
]):
    model = Notification

    async def list_for_recipient(self, recipient_id: str, limit: int = 30) -> List[Notification]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(Notification)
            .where(Notification.recipient_id == recipient_id, Notification.deleted == False)
            .order_by(Notification.date_created.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_read(self, notification_id: str) -> None:
        session = get_db_session_from_context()
        row = await session.get(Notification, notification_id)
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
    model = NotificationDispatch


@inject
class NotificationPreferenceRepo(GenericRepo[
    NotificationPreference,
    UpsertNotificationPreferenceDto,
    UpsertNotificationPreferenceDto,
    QueryNotificationDto,
    SearchNotificationDto,
]):
    model = NotificationPreference

    async def get_for_user_and_event(
        self, user_id: str, event_type: str
    ) -> Optional[NotificationPreference]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
                NotificationPreference.deleted == False,
            )
        )
        return result.scalars().first()

    async def list_for_user(self, user_id: str) -> List[NotificationPreference]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.deleted == False,
            )
        )
        return list(result.scalars().all())
