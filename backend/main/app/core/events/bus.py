"""The event bus itself (PRD §4.8) — a process-local synchronous dispatcher."""
from __future__ import annotations

from typing import Awaitable, Callable, List

from kink import di

from main.app.core.events.events import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """Publishes each domain event once to every registered subscriber.

    Subscribers are awaited in registration order; each is wrapped so one failure never
    stops the others or propagates into the emitting transaction (best-effort, §4.8). A
    subscriber that writes to the DB joins the caller's transaction, so its write is atomic
    with the domain change that produced the event.
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
                await handler(event)
            except Exception:  # noqa: BLE001 — one subscriber must never break another
                pass


async def publish_domain_event(event: DomainEvent) -> None:
    """Resolve the bus from DI and publish — safe to call from any async service method.

    Best-effort: a missing bus or a subscriber error never breaks the emitting transaction.
    """
    try:
        bus = di[EventBus]
    except Exception:
        return
    await bus.publish(event)
