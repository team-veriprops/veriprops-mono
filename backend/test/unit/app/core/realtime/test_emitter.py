"""VerificationEventEmitter (§4.9): scoped fan-out, best-effort publish, clean
subscriber teardown, and the DI-resolved publish helper that never raises."""
import asyncio

import pytest
from kink import di

from main.app.core.realtime.emitter import (
    VerificationEventEmitter,
    VerificationEventType,
    publish_verification_event,
)


class TestFanOut:
    async def test_subscriber_receives_published_event(self):
        emitter = VerificationEventEmitter()
        async with emitter.subscribe("v-1") as queue:
            emitter.publish("v-1", VerificationEventType.STATUS_CHANGED, {"status": "PAID"})
            payload = await asyncio.wait_for(queue.get(), timeout=1)
        assert payload == {"event": "status_changed", "data": {"status": "PAID"}}

    async def test_publish_is_scoped_to_the_verification(self):
        emitter = VerificationEventEmitter()
        async with emitter.subscribe("v-1") as q1, emitter.subscribe("v-2") as q2:
            emitter.publish("v-1", VerificationEventType.TASK_UPDATED, {"role": "REGISTRY"})
            assert q2.empty()
            payload = await asyncio.wait_for(q1.get(), timeout=1)
        assert payload["event"] == "task_updated"

    async def test_multiple_subscribers_all_receive(self):
        emitter = VerificationEventEmitter()
        async with emitter.subscribe("v-1") as q1, emitter.subscribe("v-1") as q2:
            emitter.publish("v-1", VerificationEventType.REPORT_RELEASED, {"version": 1})
            first = await asyncio.wait_for(q1.get(), timeout=1)
            second = await asyncio.wait_for(q2.get(), timeout=1)
        assert first == second == {"event": "report_released", "data": {"version": 1}}


class TestTeardown:
    async def test_unsubscribe_on_context_exit(self):
        emitter = VerificationEventEmitter()
        async with emitter.subscribe("v-1"):
            assert emitter.subscriber_count("v-1") == 1
        assert emitter.subscriber_count("v-1") == 0

    def test_publish_with_no_subscribers_is_noop(self):
        emitter = VerificationEventEmitter()
        emitter.publish("nobody", VerificationEventType.HEARTBEAT)  # must not raise


class TestPublishHelper:
    async def test_helper_publishes_via_di(self):
        emitter = VerificationEventEmitter()
        di[VerificationEventEmitter] = emitter
        async with emitter.subscribe("v-9") as queue:
            publish_verification_event("v-9", VerificationEventType.STATUS_CHANGED, {"ok": True})
            payload = await asyncio.wait_for(queue.get(), timeout=1)
        assert payload["data"] == {"ok": True}

    def test_helper_swallows_a_failing_publish(self):
        class _Boom(VerificationEventEmitter):
            def publish(self, *a, **k):
                raise RuntimeError("broker down")

        di[VerificationEventEmitter] = _Boom()
        try:
            # A real-time push must never break the caller's transaction (§4.9).
            publish_verification_event("v-x", VerificationEventType.STATUS_CHANGED)
        finally:
            di[VerificationEventEmitter] = VerificationEventEmitter()
