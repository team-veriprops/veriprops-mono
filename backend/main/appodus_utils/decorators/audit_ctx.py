from __future__ import annotations

from contextvars import ContextVar, Token
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
    """Discard the pending queue."""
    _pending.set(None)


def begin_audit_scope() -> Token:
    """Give an outermost transaction its own empty queue; pass the token to `end_audit_scope`.

    A transaction opened inside another (an independent write inside a request) shares the
    caller's context, so it must not reset the caller's queue: that would silently drop every
    audit row the caller queued before the nested call.
    """
    return _pending.set(None)


def end_audit_scope(token: Token) -> None:
    """Restore the queue that was current before `begin_audit_scope`."""
    _pending.reset(token)
