"""Event bus (§4.8): one publish fans to every subscriber, best-effort (one failure never
stops another), and pure SSE nudges carry no type."""
import pytest

from main.app.core.events.bus import EventBus
from main.app.core.events.events import DomainEvent, EventType


async def test_publish_fans_to_all_subscribers():
    seen = []
    bus = EventBus()
    bus.subscribe(lambda e: _record(seen, "a", e))
    bus.subscribe(lambda e: _record(seen, "b", e))

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED, verification_id="v-1"))

    assert [name for name, _ in seen] == ["a", "b"]
    assert all(evt.verification_id == "v-1" for _, evt in seen)


async def test_one_failing_subscriber_never_stops_the_others():
    seen = []
    bus = EventBus()

    async def _boom(_e):
        raise RuntimeError("subscriber blew up")

    bus.subscribe(_boom)
    bus.subscribe(lambda e: _record(seen, "b", e))

    # Must not raise — the bus isolates each subscriber.
    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED))
    assert [name for name, _ in seen] == ["b"]


def test_pure_sse_nudge_has_no_type():
    event = DomainEvent(verification_id="v-1", sse_event="task_updated")
    assert event.type is None


async def _record(sink, name, event):
    sink.append((name, event))
