"""Deliberate one-shot fault injection, for drills that must run against a live stack.

PRD §26.11 makes "failure fallback tested (kill the bot, observe the auto-reply + alert)" a
hard launch gate, and §26.6.5 is the behaviour it gates: an outage must answer with an
apology and a person, never with silence, because a bot that goes quiet is indistinguishable
from a scam that stopped replying.

Unit tests can prove the `except` branch does the right thing by raising inside a mock.
What they cannot prove is that a **real** failure, in a running process, reaches that branch
rather than a 500 in the webhook, a Meta retry, and a customer left with nothing — which is
exactly the failure mode the gate exists to rule out. So the drill needs a way to make one
real turn fail, and this is it.

Three properties keep a test seam from becoming a liability:

* **It refuses to arm in production.** Belt and braces on top of the dev router, which does
  not mount there at all, and `_require_non_prod()`, which 404s if it somehow did.
* **It is one-shot.** A fault is consumed by the turn that trips it, so a forgotten arm
  cannot degrade a whole environment — the next message is answered normally.
* **It is process-local and never persisted.** Nothing here survives a restart, and nothing
  here is reachable from customer input.
"""
from __future__ import annotations

import enum
from typing import Set

from main.appodus_utils.config.settings import Environment


class FaultPoint(str, enum.Enum):
    """Where a drill can make one operation fail."""

    # §26.6.5 — one WhatsApp bot turn raises, so the warm handover and the
    # `BOT_PIPELINE_FAILED` admin alert are both exercised on a live stack.
    WHATSAPP_BOT_TURN = "WHATSAPP_BOT_TURN"


class InjectedFault(RuntimeError):
    """The exception a drill raises. Distinct from any real error, so a log reader can tell
    a drill from an incident without guessing."""


_armed: Set[FaultPoint] = set()


def arm(point: FaultPoint) -> None:
    """Make the next operation at *point* fail, once.

    Raises in production rather than silently doing nothing: a caller asking for this on a
    production box is a bug worth surfacing, and a quiet no-op would let a drill "pass"
    against an environment where nothing was ever injected.
    """
    from main.app.config.settings import settings

    if settings.ENVIRONMENT == Environment.PRODUCTION:
        raise RuntimeError("Fault injection is not available in production.")
    _armed.add(point)


def consume(point: FaultPoint) -> bool:
    """Whether this operation should fail — and if so, disarm it.

    A plain set membership test on an empty set in every other environment, so the check
    costs nothing on the hot path it sits in.
    """
    if point not in _armed:
        return False
    _armed.discard(point)
    return True


def disarm_all() -> None:
    """Clear every armed fault (used by `/dev/reset`, so a scenario starts clean)."""
    _armed.clear()
