"""Process-local per-user event emitter (PRD §4.9, §N).

Fans a published event out to every live SSE subscriber for one **user** — the transport
behind the Chat and Notifications top-nav counters. Keyed by user id (unlike the
verification-keyed emitter, whose events are scoped to one verification's watchers).

Same contract as the verification emitter: best-effort (a publish never blocks and never
raises into the caller) and single-process (Redis fan-out lands with the Phase-12 event
bus, §4.8, without changing this API). The 60-second poll fallback reconciles anything a
push drops, so correctness never depends on delivery.
"""
from __future__ import annotations

import asyncio
import enum
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Optional, Set

from kink import di


class UserEventType(str, enum.Enum):
    """SSE event names for per-user pushes — must match the frontend stream listeners."""

    CHAT_MESSAGE = "chat_message"        # a new message landed in one of the user's threads
    CHAT_UNREAD = "chat_unread"          # the user's Chat unread counter changed
    NOTIFICATION = "notification"        # a new system notification (Phase 12)
    NOTIFICATION_UNREAD = "notification_unread"  # the user's Notifications counter changed
    HEARTBEAT = "heartbeat"


_QUEUE_MAXSIZE = 100


class UserEventEmitter:
    """In-memory pub/sub of per-user events, keyed by user id."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set["asyncio.Queue[dict]"]] = {}

    def publish(self, user_id: str, event: UserEventType, data: Optional[dict] = None) -> None:
        """Push ``{event, data}`` to every live subscriber for this user.

        Non-blocking and exception-free by contract (a full queue is silently dropped)."""
        payload = {"event": event.value, "data": data or {}}
        for queue in list(self._subscribers.get(user_id, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    @asynccontextmanager
    async def subscribe(self, user_id: str) -> AsyncIterator["asyncio.Queue[dict]"]:
        queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.setdefault(user_id, set()).add(queue)
        try:
            yield queue
        finally:
            subs = self._subscribers.get(user_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    self._subscribers.pop(user_id, None)

    def subscriber_count(self, user_id: str) -> int:
        return len(self._subscribers.get(user_id, ()))


def publish_user_event(user_id: str, event: UserEventType, data: Optional[dict] = None) -> None:
    """Best-effort publish resolved from DI — safe to call from any service method.

    Swallows every error (including a missing emitter) so a real-time push can never break
    the domain transaction that emitted it (§4.9)."""
    if not user_id:
        return
    try:
        emitter = di[UserEventEmitter]
    except Exception:
        return
    try:
        emitter.publish(user_id, event, data)
    except Exception:
        pass
