"""Free-text search conditions for list endpoints."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement


def contains_text(query: Optional[str], *columns) -> Optional[ColumnElement[bool]]:
    """A case-insensitive "contains" match of *query* against any of *columns*, or None when
    nothing was typed (so the caller adds no condition).

    The typed text is escaped: ``%`` and ``_`` match themselves, never every row. Columns may
    be computed expressions, such as a ``concat`` of first and last name.
    """
    text = (query or "").strip()
    if not text:
        return None
    return or_(*(column.icontains(text, autoescape=True) for column in columns))
