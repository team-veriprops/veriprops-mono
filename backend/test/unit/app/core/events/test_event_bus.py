"""Event bus (§4.8): one publish fans to every subscriber.

Best-effort by default: each subscriber runs in its own savepoint, so a failing one rolls back
only its own writes, never the publisher's transaction (an SQL error would otherwise poison it
and fail the publisher at commit), and its fault is logged once. An **atomic** event is the
opposite contract: every subscriber must succeed, and the first failure propagates so the
publisher's work rolls back with it (a broadcast page, retried whole by the next tick).
"""
from unittest.mock import MagicMock

import pytest

from main.app.core.events import bus as bus_module
from main.app.core.events.bus import EventBus
from main.app.core.events.events import DomainEvent, EventType
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def faults(monkeypatch):
    logged = []
    monkeypatch.setattr(bus_module, "log_fault_once", lambda exc, where, **_: logged.append((exc, where)))
    return logged


@pytest.fixture
def savepoints():
    """A context session in a transaction whose `begin_nested` records each savepoint's fate."""
    fates = []

    class _Savepoint:
        async def __aenter__(self):
            fates.append("open")

        async def __aexit__(self, exc_type, exc, tb):
            fates.append("rolled back" if exc_type else "released")
            return False

    session = MagicMock()
    session.in_transaction.return_value = True
    session.begin_nested = lambda: _Savepoint()
    token = db_session_ctx.set(session)
    yield fates
    db_session_ctx.reset(token)


async def _boom(_event):
    raise RuntimeError("subscriber blew up")


async def test_publish_fans_to_all_subscribers():
    seen = []
    bus = EventBus()
    bus.subscribe(lambda e: _record(seen, "a", e))
    bus.subscribe(lambda e: _record(seen, "b", e))

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED, verification_id="v-1"))

    assert [name for name, _ in seen] == ["a", "b"]
    assert all(evt.verification_id == "v-1" for _, evt in seen)


async def test_one_failing_subscriber_never_stops_the_others_and_is_logged(faults):
    seen = []
    bus = EventBus()
    bus.subscribe(_boom)
    bus.subscribe(lambda e: _record(seen, "b", e))

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED))

    assert [name for name, _ in seen] == ["b"]
    assert len(faults) == 1 and "STATUS_CHANGED" in faults[0][1] and "_boom" in faults[0][1]


async def test_each_subscriber_runs_in_its_own_savepoint(savepoints, faults):
    bus = EventBus()
    bus.subscribe(_boom)
    bus.subscribe(lambda e: _record([], "b", e))

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED))

    # The failure rolls back only its own savepoint; the next subscriber's writes still land.
    assert savepoints == ["open", "rolled back", "open", "released"]


async def test_outside_a_transaction_subscribers_run_without_a_savepoint(faults):
    seen = []
    bus = EventBus()
    bus.subscribe(lambda e: _record(seen, "a", e))

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED))

    assert [name for name, _ in seen] == ["a"]


async def test_an_atomic_event_propagates_the_first_failure(savepoints, faults):
    seen = []
    bus = EventBus()
    bus.subscribe(_boom)
    bus.subscribe(lambda e: _record(seen, "b", e))

    with pytest.raises(RuntimeError):
        await bus.publish(DomainEvent(type=EventType.BROADCAST_ANNOUNCEMENT, atomic=True))

    assert seen == []        # nothing after the failure runs
    assert faults == []      # the publisher decides what the failure means


@pytest.mark.subscriber_faults_expected
async def test_the_suite_guard_sees_a_swallowed_subscriber_failure(subscriber_faults):
    """The root conftest fails any test whose bus logs a subscriber fault it did not expect;
    this one opts in, so it can check the guard saw the fault."""
    bus = EventBus()
    bus.subscribe(_boom)

    await bus.publish(DomainEvent(type=EventType.STATUS_CHANGED))

    assert len(subscriber_faults) == 1 and "_boom" in subscriber_faults[0][1]


def test_pure_sse_nudge_has_no_type():
    event = DomainEvent(verification_id="v-1", sse_event="task_updated")
    assert event.type is None
    assert event.atomic is False


async def _record(sink, name, event):
    sink.append((name, event))
