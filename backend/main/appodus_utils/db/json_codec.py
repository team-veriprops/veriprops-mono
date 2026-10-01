"""The engine's JSON serializer: how a value is written into a JSON column.

Values reach JSON columns straight from the ORM and the domain — an entity's UUID id, a
timestamp, an enum member — and the standard encoder refuses all of them. These well-known types
are written in their wire form; anything else is still refused, so an object nobody meant to
persist fails loudly rather than being silently stringified.
"""
from __future__ import annotations

import enum
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _wire_form(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_serialize(value: Any) -> str:
    return json.dumps(value, default=_wire_form)
