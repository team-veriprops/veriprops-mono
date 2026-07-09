from __future__ import annotations

from contextvars import ContextVar
from typing import Awaitable, Callable

_pending: ContextVar[list[Callable[[], Awaitable[None]]] | None] = ContextVar(
    "_audit_pending", default=None
)


def schedule_audit_write(coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Enqueue an async write to run after the current outermost @transactional flush."""
    q = _pending.get()
    if q is None:
        q = []
        _pending.set(q)
    q.append(coro_factory)


async def drain_audit_writes() -> None:
    """Execute all queued audit writes in order, then clear the queue."""
    q = _pending.get()
    if q:
        for factory in q:
            await factory()
        q.clear()


def reset_audit_ctx() -> None:
    """Discard the pending queue (called at the start of each outermost transaction)."""
    _pending.set(None)
