"""In-process real-time transport (PRD §4.9).

A single SSE transport carries every server→client push (status changes, task
updates, conflicts, report release). This package owns the process-local pub/sub
emitter behind it; the customer tracking controller exposes the ``text/event-stream``
endpoint and the shared-shape 60-second polling fallback.

Multi-instance fan-out (Redis pub/sub) is deferred to the Phase-12 event bus (§4.8);
until then the emitter is a best-effort hint and the poll snapshot is the source of
truth, so correctness never depends on a push being delivered.
"""
from main.app.core.realtime.emitter import (
    VerificationEventEmitter,
    VerificationEventType,
    publish_verification_event,
)
from main.app.core.realtime.user_emitter import (
    UserEventEmitter,
    UserEventType,
    publish_user_event,
)

__all__ = [
    "VerificationEventEmitter",
    "VerificationEventType",
    "publish_verification_event",
    "UserEventEmitter",
    "UserEventType",
    "publish_user_event",
]
