"""Process-local verification event emitter (PRD §4.9).

Fans a published event out to every live SSE subscriber for one verification. Keyed
by verification id (the same id the customer's tracking/stream endpoints are scoped
to). Deliberately in-process and best-effort:

- **Best-effort.** A publish never blocks and never raises into the caller — an emit
  failure must not roll back the domain transaction that produced the event. The
  60-second poll fallback re-reads the authoritative snapshot, so a dropped push only
  costs latency, never correctness.
- **Single process.** Subscribers live in this worker's memory. Horizontal fan-out
  (Redis pub/sub) lands with the Phase-12 event bus (§4.8); the public API here does
  not change when that arrives.

TODO(gap): Redis multi-instance SSE fan-out — subscribers on other workers miss pushes
until then (the 60s poll fallback keeps correctness) — PRD "Known Gaps & Roadmap".
"""
from __future__ import annotations

import asyncio
import enum
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Optional, Set

from kink import di

from main.app.config.settings import settings


class VerificationEventType(str, enum.Enum):
    """SSE event names — must match the frontend ``useVerificationStream`` listeners."""

    STATUS_CHANGED = "status_changed"
    TASK_UPDATED = "task_updated"
    CONFLICT_DETECTED = "conflict_detected"
    REPORT_RELEASED = "report_released"
    HEARTBEAT = "heartbeat"


# Bound each subscriber queue so a slow/abandoned client cannot grow memory without
# limit; when full we drop the push (the poll fallback reconciles).
_QUEUE_MAXSIZE = settings.SSE_QUEUE_MAXSIZE


class VerificationEventEmitter:
    """In-memory pub/sub of verification events, keyed by verification id."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set["asyncio.Queue[dict]"]] = {}

    def publish(self, verification_id: str, event: VerificationEventType, data: Optional[dict] = None) -> None:
        """Push ``{event, data}`` to every live subscriber for this verification.

        Non-blocking and exception-free by contract (a full queue is silently dropped).
        """
        payload = {"event": event.value, "data": data or {}}
        for queue in list(self._subscribers.get(verification_id, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow client — the poll fallback will reconcile

    @asynccontextmanager
    async def subscribe(self, verification_id: str) -> AsyncIterator["asyncio.Queue[dict]"]:
        """Register a subscriber queue for the lifetime of the ``async with`` block."""
        queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.setdefault(verification_id, set()).add(queue)
        try:
            yield queue
        finally:
            subs = self._subscribers.get(verification_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    self._subscribers.pop(verification_id, None)

    def subscriber_count(self, verification_id: str) -> int:
        return len(self._subscribers.get(verification_id, ()))


def publish_verification_event(
    verification_id: str, event: VerificationEventType, data: Optional[dict] = None
) -> None:
    """Best-effort publish resolved from DI — safe to call from any service method.

    Swallows every error (including a missing/registered emitter) so a real-time push
    can never break the domain transaction that emitted it (§4.9).
    """
    try:
        emitter = di[VerificationEventEmitter]
    except Exception:
        return
    try:
        emitter.publish(verification_id, event, data)
    except Exception:
        pass
