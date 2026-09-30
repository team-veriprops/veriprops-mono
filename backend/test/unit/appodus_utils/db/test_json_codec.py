"""What a JSON column accepts (every `jsonb_variant()` column, via the engine's serializer).

Audit details, notification data and payloads carry ids and timestamps straight from the ORM;
a UUID or a datetime that the standard encoder refuses turned an admin note into a 500. The
engine's serializer writes those well-known types in their wire form and still refuses anything
else, so an object nobody meant to persist fails loudly instead of being stringified.
"""
import enum
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from main.appodus_utils.db.json_codec import json_serialize


class _Colour(str, enum.Enum):
    RED = "RED"


def test_ids_timestamps_enums_and_decimals_are_written_in_their_wire_form():
    note_id = uuid.UUID("01a0f380-183d-78d1-84db-656d2b5bca5f")
    at = datetime(2026, 9, 30, 12, 30, tzinfo=timezone.utc)
    encoded = json_serialize({
        "note_id": note_id, "at": at, "on": date(2026, 9, 30), "colour": _Colour.RED, "amount": Decimal("12.50"),
    })
    assert json.loads(encoded) == {
        "note_id": str(note_id), "at": at.isoformat(), "on": "2026-09-30", "colour": "RED", "amount": "12.50",
    }


def test_anything_else_is_still_refused():
    with pytest.raises(TypeError):
        json_serialize({"session": object()})


def test_plain_json_is_unchanged():
    assert json.loads(json_serialize({"a": [1, "x", None, True]})) == {"a": [1, "x", None, True]}


@pytest.mark.parametrize("independent", [False, True])
def test_every_engine_writes_json_through_it(independent):
    from main.appodus_utils.db.session import create_db_engine_for_env

    engine = create_db_engine_for_env(independent=independent)
    assert engine.dialect._json_serializer is json_serialize
