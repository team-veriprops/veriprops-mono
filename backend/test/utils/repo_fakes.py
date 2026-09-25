"""In-memory stand-ins for `GenericRepo.insert_or_get` / `upsert` / `claim_transition`, for service unit tests.

A test that fakes a repo supplies how to find the row holding a key and how to create one;
these helpers turn that into the real methods' contract, so a service under test sees the
same "created or already there" answers it gets from Postgres.
"""
import enum
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock


def fake_insert_or_get(
        find: Callable[[Dict[str, Any]], Any],
        create: Callable[[Dict[str, Any]], Any],
) -> AsyncMock:
    """`insert_or_get(values, conflict_columns=None, *, unique_index=None) -> (row, created)`.

    *find(values)* returns the live row holding the key, or None; *create(values)* stores and
    returns a new one (sync or async).
    """
    async def _insert_or_get(values, conflict_columns=None, *, unique_index=None):
        existing = find(values)
        if existing is not None:
            return existing, False
        row = create(values)
        if hasattr(row, "__await__"):
            row = await row
        return row, True

    return AsyncMock(side_effect=_insert_or_get)


def fake_upsert(
        find: Callable[[Dict[str, Any]], Any],
        create: Callable[[Dict[str, Any]], Any],
) -> AsyncMock:
    """`upsert(values, update_columns, conflict_columns=None, *, unique_index=None) -> row`."""
    async def _upsert(values, update_columns: List[str], conflict_columns=None, *, unique_index=None):
        existing = find(values)
        if existing is None:
            row = create(values)
            return await row if hasattr(row, "__await__") else row
        for column in update_columns:
            setattr(existing, column, values[column])
        return existing

    return AsyncMock(side_effect=_upsert)


def first_matching(rows: List[Any], **match: Any) -> Optional[Any]:
    """The first live row whose attributes equal *match* (a `find` for the fakes above)."""
    for row in rows:
        if getattr(row, "deleted", False):
            continue
        if all(getattr(row, key) == value for key, value in match.items()):
            return row
    return None


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, enum.Enum) else value


def fake_claim_transition(rows: Union[Dict[Any, Any], Callable[[Any], Any]]) -> AsyncMock:
    """`claim_transition(_id, from_statuses, to_status=None, *, status_column="status",
    expect=None, increments=None, **values) -> row | None`.

    *rows* maps an id to its row (or is a function doing that lookup). The row is moved only
    while its status is one of *from_statuses* and it still matches *expect*, so a second
    claim of the same move gets None — as the losing request does against Postgres. A model
    column passed as a value (`frozen_from_status=Commission.status`) copies that column's
    value from before the move.
    """
    find = rows.get if isinstance(rows, dict) else rows

    async def _claim(_id, from_statuses, to_status=None, *, status_column="status",
                     expect=None, increments=None, **values):
        row = find(_id)
        if row is None or getattr(row, "deleted", False) is True:
            return None
        if getattr(row, status_column) not in {_plain(s) for s in from_statuses}:
            return None
        if any(getattr(row, key) != _plain(value) for key, value in (expect or {}).items()):
            return None
        # Every right-hand side reads the row as it was, as SQL's SET does.
        before = dict(vars(row)) if hasattr(row, "__dict__") else {}
        for key, step in (increments or {}).items():
            setattr(row, key, (getattr(row, key) or 0) + step)
        for key, value in values.items():
            column = getattr(value, "key", None)
            setattr(row, key, before.get(column) if column is not None else _plain(value))
        if to_status is not None:
            setattr(row, status_column, _plain(to_status))
        return row

    return AsyncMock(side_effect=_claim)
