"""Notification service — emit in-app notifications and dispatch external channels."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Any

from kink import di, inject

from main.app.domain.notification.events import render_title, render_body
from main.app.domain.notification.models import (
    CreateNotificationDto,
    NotificationDispatch,
    NotificationDto,
    NotificationEvent,
    NotificationPreferenceDto,
    UpsertNotificationPreferenceDto,
)
from main.app.domain.notification.repo import (
    NotificationDispatchRepo,
    NotificationPreferenceRepo,
    NotificationRepo,
)
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class NotificationService:
    def __init__(
        self,
        repo: NotificationRepo,
        dispatch_repo: NotificationDispatchRepo,
        pref_repo: NotificationPreferenceRepo,
    ):
        self._repo = repo
        self._dispatch_repo = dispatch_repo
        self._pref_repo = pref_repo

    async def emit(
        self,
        event: NotificationEvent,
        recipient_id: str,
        context: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> NotificationDto:
        """Write an in-app notification row.

        External dispatch (email/SMS/push) is deliberately skipped here — it is
        handled by VerificationMessages which is called by individual services.
        This keeps the in-app record always written even when ENABLE_OUT_MESSAGING
        is False.
        """
        title = render_title(event, context)
        body = render_body(event, context)

        row = await self._repo.create(CreateNotificationDto(
            recipient_id=recipient_id,
            event_type=event.value,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        ))
        return self._to_dto(row)

    async def list_for_recipient(self, recipient_id: str, limit: int = 30) -> List[NotificationDto]:
        rows = await self._repo.list_for_recipient(recipient_id, limit=limit)
        return [self._to_dto(r) for r in rows]

    async def mark_read(self, notification_id: str, recipient_id: str) -> None:
        row = await self._repo.get_model(notification_id)
        if row is None or row.recipient_id != recipient_id:
            raise ResourceNotFoundException(resource="Notification")
        await self._repo.mark_read(notification_id)

    # ── Preferences ───────────────────────────────────────────────

    async def get_preferences(self, user_id: str) -> List[NotificationPreferenceDto]:
        rows = await self._pref_repo.list_for_user(user_id)
        return [self._pref_to_dto(r) for r in rows]

    async def upsert_preference(
        self, user_id: str, dto: UpsertNotificationPreferenceDto
    ) -> NotificationPreferenceDto:
        existing = await self._pref_repo.get_for_user_and_event(user_id, dto.event_type)
        if existing:
            await self._pref_repo.update(str(existing.id), UpsertNotificationPreferenceDto(
                event_type=dto.event_type,
                email_enabled=dto.email_enabled,
                sms_enabled=dto.sms_enabled,
                push_enabled=dto.push_enabled,
            ))
            row = await self._pref_repo.get_model(str(existing.id))
        else:
            dto_with_user = UpsertNotificationPreferenceDto(
                event_type=dto.event_type,
                email_enabled=dto.email_enabled,
                sms_enabled=dto.sms_enabled,
                push_enabled=dto.push_enabled,
            )
            row = await self._pref_repo.create(dto_with_user)
            # Patch user_id — GenericRepo.create uses model fields from dto
            from main.appodus_utils.db.session import get_db_session_from_context
            session = get_db_session_from_context()
            row.user_id = user_id
        return self._pref_to_dto(row)

    # ── Helpers ───────────────────────────────────────────────────

    def _to_dto(self, row) -> NotificationDto:
        return NotificationDto(
            id=str(row.id),
            recipient_id=row.recipient_id,
            event_type=row.event_type,
            title=row.title,
            body=row.body,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            read=row.read,
            date_created=str(row.date_created),
        )

    def _pref_to_dto(self, row) -> NotificationPreferenceDto:
        return NotificationPreferenceDto(
            user_id=row.user_id,
            event_type=row.event_type,
            email_enabled=row.email_enabled,
            sms_enabled=row.sms_enabled,
            push_enabled=row.push_enabled,
        )
