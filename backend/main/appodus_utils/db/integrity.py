"""Turning a specific unique-index violation into the error the caller should see."""
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy.exc import IntegrityError

from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.exception.faults import expecting_violation, violated_constraint


@asynccontextmanager
async def unique_violation_as(index_name: str, error: Callable[[], Exception]) -> AsyncIterator[None]:
    """Run the block's writes in a savepoint; a violation of *index_name* raises ``error()``.

    For a write whose conflict is a legitimate outcome rather than a bug, where
    `insert_or_get` can't express it (the violated guard is not the conflict target, or the
    write is an update): "that number is already linked", "that code is taken". The savepoint
    keeps the transaction usable, and a violation of any *other* constraint re-raises
    unchanged, so a real bug is never disguised as a domain answer.
    """
    session = get_db_session_from_context()
    try:
        # Declared expected, so the layers it passes through don't log the answer as a fault.
        with expecting_violation(index_name):
            async with session.begin_nested():
                yield
                await session.flush()
    except IntegrityError as exc:
        if index_name in violated_constraint(exc):
            raise error() from None
        raise
