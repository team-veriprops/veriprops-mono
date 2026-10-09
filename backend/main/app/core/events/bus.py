"""The event bus itself (PRD §4.8) — a process-local synchronous dispatcher."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Awaitable, Callable, List

from kink import di

from main.app.core.events.events import DomainEvent
from main.appodus_utils.db.session import get_db_session_or_none
from main.appodus_utils.exception.faults import log_fault_once

EventHandler = Callable[[DomainEvent], Awaitable[None]]


def _savepoint():
    """A savepoint on the context session while it is in a transaction; otherwise nothing.

    A subscriber that writes joins the publisher's transaction, so its write is atomic with the
    domain change behind the event. Without its own savepoint, one failed statement aborts that
    whole transaction: the bus would swallow the error and the publisher would then fail at
    commit, which is the opposite of best-effort.
    """
    session = get_db_session_or_none()
    if session is not None and session.in_transaction():
        return session.begin_nested()
    return nullcontext()


class EventBus:
    """Publishes each domain event once to every registered subscriber.

    Subscribers are awaited in registration order, each in its own savepoint. By default
    delivery is best-effort: a failing subscriber rolls back only its own writes, its fault is
    logged once, and the others still run. An `atomic` event propagates the first failure
    instead, so the publisher's work rolls back with it.
    """

    def __init__(self) -> None:
        self._subscribers: List[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    def clear(self) -> None:
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def publish(self, event: DomainEvent) -> None:
        for handler in list(self._subscribers):
            try:
                async with _savepoint():
                    await handler(event)
            except Exception as exc:
                if event.atomic:
                    raise
                name = getattr(handler, "__name__", repr(handler))
                log_fault_once(exc, f"event {event.type.value if event.type else event.sse_event}: subscriber {name}")


async def publish_domain_event(event: DomainEvent) -> None:
    """Resolve the bus from DI and publish — safe to call from any async service method.

    Best-effort unless the event is atomic: a missing bus or a subscriber error never breaks
    the emitting transaction.
    """
    try:
        bus = di[EventBus]
    except Exception:
        return
    await bus.publish(event)
