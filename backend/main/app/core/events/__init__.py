"""In-process synchronous event bus (PRD §4.8).

Every domain event is published **once**; subscribers decide surfacing:
- ``RealtimeSubscriber`` re-emits the verification-keyed + per-user SSE pushes (§4.9).
- ``NotificationSubscriber`` consults the declarative rule table (`notification/rules.py`)
  to create in-app notifications and fan out email/SMS via the existing senders.
- ``ChatCounterSubscriber`` pushes the Chat unread counter for chat events (§12.3).

Not Kafka — a synchronous dispatcher backed by the existing DB. Publishing is best-effort
per subscriber (one failing subscriber never breaks another or the emitting transaction).
Redis fan-out can replace the dispatcher internals later without changing this API (D15/D20).
"""
from main.app.core.events.events import DomainEvent, EventType
from main.app.core.events.bus import EventBus, publish_domain_event

__all__ = ["DomainEvent", "EventType", "EventBus", "publish_domain_event"]
