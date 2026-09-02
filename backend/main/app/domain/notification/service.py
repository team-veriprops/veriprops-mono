"""Notification service (PRD §12).

Turns a published domain event into per-recipient in-app notifications and (subject to the
rule table + the user's opt-outs) email/SMS fan-out. Also serves the feed, the unread
counter, and mark-read. In-app is always created (§12.1); external dispatch is best-effort so
a template/provider hiccup never breaks the emitting transaction.
"""
from __future__ import annotations

from typing import List

from kink import di, inject

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
        self._notification_repo = notification_repo
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
                await self._notification_repo.create_return_model(
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
            await self._dispatch_whatsapp(event, user_id, rule)

        # Delegates are not users, so they never appear in `recipient_user_ids` — their
        # fan-out is a second audience on the same event (D65), resolved once for the case
        # rather than once per recipient.
        await self._dispatch_delegates(event, rule)

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

    # ── WhatsApp milestones (§7.6.2, D65) ─────────────────────────────
    #
    # A separate branch rather than a third entry in the channel list above, because the
    # WhatsApp recipient is resolved somewhere else entirely: `email`/`sms` address the
    # user's profile, while a §7.7 template may only go to the number that account
    # OTP-verified (§7.4.3). That asymmetry is the price of the link being the join key,
    # and D65 names it rather than hiding it. What stays identical is the important part —
    # the consent check happens **here**, in the router, never at a send site.

    async def _dispatch_whatsapp(self, event: DomainEvent, user_id: str, rule) -> None:
        if not rule.whatsapp or not rule.whatsapp_template:
            return
        try:
            await self._milestones().send_customer_milestone(
                user_id, event.verification_id, rule.whatsapp_template
            )
        except Exception:  # noqa: BLE001 — a milestone never breaks the emitting transaction
            pass

    async def _dispatch_delegates(self, event: DomainEvent, rule) -> None:
        """The §7.4.5 audience: a case's authorized delegate hears the same four moments.

        Always as `delegate_status`, never as the customer's template — which is what
        makes "status milestones only, never documents or reports" structural rather than
        a rule someone has to remember: `delegate_status` has no link parameter to fill.
        """
        if not rule.whatsapp or not event.verification_id:
            return
        try:
            await self._delegates().notify_milestone(event.verification_id)
        except Exception:  # noqa: BLE001 — same best-effort posture as every other fan-out
            pass

    @staticmethod
    def _delegates():
        from main.app.domain.verification.delegate.service import CaseDelegateService

        return di[CaseDelegateService]

    @staticmethod
    def _milestones():
        """Resolved lazily so the notification domain never hard-depends on the channel.

        The rule table is generic; WhatsApp is one consumer of it. Importing the channel at
        module scope would invert that and close an import cycle through the message domain.
        """
        from main.app.domain.channel.whatsapp.milestones import WhatsAppMilestoneSender

        return di[WhatsAppMilestoneSender]

    # ── Feed / counter / read ─────────────────────────────────────────

    async def feed(self, user_id: str, page: int, page_size: int) -> Page[NotificationDto]:
        rows, total = await self._notification_repo.list_for_user(user_id, page, page_size)
        dtos = [self._to_dto(n) for n in rows]
        return self._notification_repo._db_utils.build_page(dtos, total, page, page_size)

    async def unread_count(self, user_id: str) -> int:
        return await self._notification_repo.unread_count(user_id)

    async def mark_read(self, notification_id: str, user_id: str) -> None:
        notification = await self._notification_repo.get_model(notification_id)
        if notification is None or notification.user_id != user_id:
            return
        notification.read = True
        self._notification_repo._session.add(notification)

    async def mark_all_read(self, user_id: str) -> int:
        return await self._notification_repo.mark_all_read(user_id)

    @staticmethod
    def _to_dto(n: Notification) -> NotificationDto:
        return NotificationDto(
            id=n.id, type=n.type, title=n.title, body=n.body, link=n.link,
            read=n.read, event_ref=n.event_ref, date_created=n.date_created,
        )
