"""Transaction-scoped Postgres advisory locks, for writes no unique index can guard.

Some writes are only correct when concurrent callers take turns: replacing a whole set of
rows (a tier's line items, an agent's coverage), or a one-open-request rule that no unique
index can describe. `advisory_xact_lock` makes a second caller wait until the first
transaction commits or rolls back, and then read what the first wrote.

The lock is keyed by a string, namespaced by the caller (`"agent_coverage:<id>"`) and
hashed to Postgres's 64-bit lock space, and it is released automatically when the
transaction ends. Call it inside a transaction (any `@transactional` method).
"""
from sqlalchemy import func, select

from main.appodus_utils.db.session import get_db_session_from_context


def _key(name: str):
    return func.hashtextextended(name, 0)


async def advisory_xact_lock(name: str) -> None:
    """Block until this transaction holds the lock *name*."""
    await get_db_session_from_context().execute(select(func.pg_advisory_xact_lock(_key(name))))


async def try_advisory_xact_lock(name: str) -> bool:
    """Take the lock *name* if it is free; False (without waiting) if another transaction has it."""
    result = await get_db_session_from_context().execute(select(func.pg_try_advisory_xact_lock(_key(name))))
    return bool(result.scalar_one())
