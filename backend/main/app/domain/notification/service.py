"""Notification service (PRD §12).

Turns a published domain event into per-recipient in-app notifications and (subject to the
rule table + the user's opt-outs) email/SMS fan-out. Also serves the feed, the unread
counter, and mark-read. In-app is always created (§12.1); external dispatch is best-effort so
a template/provider hiccup never breaks the emitting transaction.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.core.events.events import DomainEvent
from main.app.core.realtime.user_emitter import UserEventType, publish_user_event
from main.app.domain.notification.content import build_content, external_context
from main.app.domain.notification.models import (
    CreateNotificationDto,
    Notification,
    NotificationDto,
)
from main.app.domain.notification.dispatcher import NotificationDispatcher
from main.app.domain.notification.repo import NotificationRepo
from main.app.domain.notification.rules import rule_for
from main.app.domain.notification_preference.service import NotificationPreferenceService
from main.appodus_utils import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.models import MessageChannel


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class NotificationService:
    def __init__(
        self,
        notification_repo: NotificationRepo,
        preferences: NotificationPreferenceService,
        dispatcher: NotificationDispatcher,
    ):
        self._repo = notification_repo
        self._preferences = preferences
        self._dispatcher = dispatcher

    async def create_for_event(self, event: DomainEvent) -> None:
        """Fan an event out per the §4.8 rule table. Chat-only events create no notification."""
        if event.type is None or not event.recipient_user_ids:
            return  # a pure SSE-refresh nudge, or an event with no recipients
        rule = rule_for(event.type)
        if rule.chat_only:
            return

        title, body, link = build_content(event)
        for user_id in dict.fromkeys(event.recipient_user_ids):  # de-dupe, preserve order
            if rule.in_app:
                await self._repo.create_return_model(
                    CreateNotificationDto(
                        user_id=user_id,
                        type=event.type.value,
                        title=title,
                        body=body,
                        link=link,
                        event_ref=event.verification_id,
                    )
                )
                publish_user_event(user_id, UserEventType.NOTIFICATION, {"type": event.type.value})
                publish_user_event(user_id, UserEventType.NOTIFICATION_UNREAD, {})

            await self._dispatch_external(event, user_id, rule)

    async def _dispatch_external(self, event: DomainEvent, user_id: str, rule) -> None:
        if not rule.template or not (rule.email or rule.sms):
            return
        email_ok, sms_ok = await self._preferences.channels_enabled(user_id, event.type.value)
        channels: List[MessageChannel] = []
        if rule.email and email_ok:
            channels.append(MessageChannel.EMAIL)
        if rule.sms and sms_ok:
            channels.append(MessageChannel.SMS)
        if not channels:
            return
        try:
            await self._dispatcher.dispatch(user_id, rule.template, channels, external_context(event))
        except Exception:  # noqa: BLE001 — external send is best-effort, never fatal
            pass

    # ── Feed / counter / read ─────────────────────────────────────────

    async def feed(self, user_id: str, page: int, page_size: int) -> Page[NotificationDto]:
        raw = await self._repo.list_for_user(user_id, page, page_size)
        items = [self._to_dto(n) for n in raw.items]
        return Page[NotificationDto](items=items, meta=raw.meta)

    async def unread_count(self, user_id: str) -> int:
        return await self._repo.unread_count(user_id)

    async def mark_read(self, notification_id: str, user_id: str) -> None:
        notification = await self._repo.get_model(notification_id)
        if notification is None or notification.user_id != user_id:
            return
        notification.read = True
        self._repo._session.add(notification)

    async def mark_all_read(self, user_id: str) -> int:
        return await self._repo.mark_all_read(user_id)

    @staticmethod
    def _to_dto(n: Notification) -> NotificationDto:
        return NotificationDto(
            id=n.id, type=n.type, title=n.title, body=n.body, link=n.link,
            read=n.read, event_ref=n.event_ref, date_created=n.date_created,
        )
