"""Notification preference service (PRD §12.4)."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from kink import inject

from main.app.core.events.events import EventType
from main.app.domain.notification.rules import RULES
from main.app.domain.notification_preference.catalogue import (
    PREFERENCE_COPY,
    ChannelMode,
    audiences_for,
    channel_modes,
    configurable_events,
)
from main.app.domain.notification_preference.models import (
    CreateNotificationPreferenceDto,
    PreferenceDto,
    SetPreferenceDto,
)
from main.app.domain.notification_preference.repo import NotificationPreferenceRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class NotificationPreferenceService:
    def __init__(self, preference_repo: NotificationPreferenceRepo):
        self._preference_repo = preference_repo

    async def list_for_user(
            self, user_id: str, user_type: Optional[str], personas: Sequence[str],
    ) -> List[PreferenceDto]:
        """Every event this user may change (§12.4), with the platform default applied where
        they have recorded no override."""
        rows = {r.event_type: r for r in await self._preference_repo.list_for_user(user_id)}
        prefs = []
        for event in configurable_events(audiences_for(user_type, personas)):
            row = rows.get(event.value)
            prefs.append(_preference(
                event,
                email=row.email_enabled if row else True,
                sms=row.sms_enabled if row else True,
            ))
        return prefs

    async def set(
            self, user_id: str, user_type: Optional[str], personas: Sequence[str], dto: SetPreferenceDto,
    ) -> PreferenceDto:
        """Record an opt-out override. Only an event addressed to this user, and only its
        optional channels, can change; a required channel stays on."""
        if dto.event_type not in configurable_events(audiences_for(user_type, personas)):
            raise ValidationException(message="You can't change notifications for that event.")
        email_mode, sms_mode = channel_modes(RULES[dto.event_type])
        # One statement on the live (user, event) key, so concurrent saves can't create twins.
        row = await self._preference_repo.upsert(
            CreateNotificationPreferenceDto(
                user_id=user_id,
                event_type=dto.event_type.value,
                email_enabled=dto.email_enabled if email_mode == ChannelMode.OPTIONAL else email_mode == ChannelMode.REQUIRED,
                sms_enabled=dto.sms_enabled if sms_mode == ChannelMode.OPTIONAL else False,
            ).model_dump(by_alias=False),
            ["email_enabled", "sms_enabled"],
            unique_index="uq_notif_prefs_user_event",
        )
        return _preference(dto.event_type, email=row.email_enabled, sms=row.sms_enabled)

    async def channels_enabled(self, user_id: str, event_type: str) -> Tuple[bool, bool]:
        """(email_enabled, sms_enabled) for a user + event — platform default (on, on) unless
        the user has recorded an opt-out override."""
        row = await self._preference_repo.get_one(user_id, event_type)
        if row is None:
            return True, True
        return row.email_enabled, row.sms_enabled


def _preference(event: EventType, *, email: bool, sms: bool) -> PreferenceDto:
    """The page's view of one event: a required channel is on and an unused one off, whatever
    a stored row says."""
    copy = PREFERENCE_COPY[event]
    email_mode, sms_mode = channel_modes(RULES[event])
    return PreferenceDto(
        event_type=event, label=copy.label, description=copy.description,
        email_mode=email_mode, sms_mode=sms_mode,
        email_enabled=_effective(email_mode, email), sms_enabled=_effective(sms_mode, sms),
    )


def _effective(mode: ChannelMode, stored: bool) -> bool:
    if mode == ChannelMode.OPTIONAL:
        return stored
    return mode == ChannelMode.REQUIRED
