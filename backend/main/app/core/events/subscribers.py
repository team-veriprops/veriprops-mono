"""Event-bus subscribers (PRD §4.8, §12.3).

Three subscribers decide how each published event surfaces:
- ``realtime_subscriber`` re-emits the verification-keyed SSE push, preserving the exact
  S13 event names so the customer tracking hooks are untouched (D15/D20).
- ``notification_subscriber`` creates in-app notifications + email/SMS fan-out per the rule
  table (`notification/rules.py`) and the user's preferences.
- ``chat_counter_subscriber`` pushes the per-user Chat counter for chat events (§12.3) — a
  routine message bumps the counter only; the rule table keeps it out of Notifications.

Handlers resolve their services from DI at call time and are registered on the bus at
bootstrap. Each is best-effort by the bus contract (one failure never breaks another).
"""
from __future__ import annotations

from kink import di

from main.app.core.events.bus import EventBus
from main.app.core.events.events import DomainEvent, EventType
from main.app.core.realtime.emitter import VerificationEventEmitter, VerificationEventType
from main.app.core.realtime.user_emitter import UserEventEmitter, UserEventType


async def realtime_subscriber(event: DomainEvent) -> None:
    """Re-emit the verification-keyed SSE push (S13 preservation)."""
    if not event.verification_id or not event.sse_event:
        return
    try:
        emitter = di[VerificationEventEmitter]
        emitter.publish(event.verification_id, VerificationEventType(event.sse_event), event.data)
    except Exception:  # noqa: BLE001
        pass


async def notification_subscriber(event: DomainEvent) -> None:
    """Create in-app notifications + external fan-out per the §4.8 rule table."""
    from main.app.domain.notification.service import NotificationService

    service = di[NotificationService]
    await service.create_for_event(event)


async def chat_counter_subscriber(event: DomainEvent) -> None:
    """Push the per-user Chat counter for chat events (§12.3 — counter only, no notification)."""
    if event.type != EventType.MESSAGE_SENT:
        return
    try:
        emitter = di[UserEventEmitter]
        for user_id in event.recipient_user_ids:
            emitter.publish(user_id, UserEventType.CHAT_MESSAGE, event.data)
            emitter.publish(user_id, UserEventType.CHAT_UNREAD, {})
    except Exception:  # noqa: BLE001
        pass


def register_subscribers(bus: EventBus) -> None:
    """Wire the standard subscribers onto the bus (idempotent — clears first)."""
    bus.clear()
    bus.subscribe(realtime_subscriber)
    bus.subscribe(notification_subscriber)
    bus.subscribe(chat_counter_subscriber)
