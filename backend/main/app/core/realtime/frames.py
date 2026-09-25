"""The one SSE frame encoder, shared by the verification and per-user streams (§4.9).

Payloads come from domain events, which often carry ids straight off ORM rows. A value
`json.dumps` cannot encode would raise inside the stream and end it for that client, losing
every push after it, so ids are written in their wire form — the 32-char hex the DTOs send.
"""
from __future__ import annotations

import json
import uuid
from typing import Any


def _wire(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return value.hex
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def sse_frame(event: str, data: dict) -> str:
    """One `text/event-stream` message: the event name, then its JSON payload."""
    return f"event: {event}\ndata: {json.dumps(data, default=_wire)}\n\n"
