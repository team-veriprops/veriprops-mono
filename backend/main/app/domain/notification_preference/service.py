"""Notification preference service (PRD §12.4)."""
from __future__ import annotations

from typing import List, Tuple

from kink import inject

from main.app.domain.notification_preference.models import (
    CreateNotificationPreferenceDto,
    PreferenceDto,
    SetPreferenceDto,
)
from main.app.domain.notification_preference.repo import NotificationPreferenceRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class NotificationPreferenceService:
    def __init__(self, preference_repo: NotificationPreferenceRepo):
        self._preference_repo = preference_repo

    async def list_for_user(self, user_id: str) -> List[PreferenceDto]:
        rows = await self._preference_repo.list_for_user(user_id)
        return [
            PreferenceDto(
                event_type=r.event_type, email_enabled=r.email_enabled, sms_enabled=r.sms_enabled
            )
            for r in rows
        ]

    async def set(self, user_id: str, dto: SetPreferenceDto) -> PreferenceDto:
        existing = await self._preference_repo.get_one(user_id, dto.event_type)
        if existing:
            existing.email_enabled = dto.email_enabled
            existing.sms_enabled = dto.sms_enabled
            self._preference_repo._session.add(existing)
            row = existing
        else:
            row = await self._preference_repo.create_return_model(
                CreateNotificationPreferenceDto(
                    user_id=user_id,
                    event_type=dto.event_type,
                    email_enabled=dto.email_enabled,
                    sms_enabled=dto.sms_enabled,
                )
            )
        return PreferenceDto(
            event_type=row.event_type, email_enabled=row.email_enabled, sms_enabled=row.sms_enabled
        )

    async def channels_enabled(self, user_id: str, event_type: str) -> Tuple[bool, bool]:
        """(email_enabled, sms_enabled) for a user + event — platform default (on, on) unless
        the user has recorded an opt-out override."""
        row = await self._preference_repo.get_one(user_id, event_type)
        if row is None:
            return True, True
        return row.email_enabled, row.sms_enabled
