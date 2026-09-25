"""One run of a scheduled job at a time, across every worker process.

Each worker process starts its own scheduler (`app/jobs/scheduled.py`), so without a guard
every sweep fires once per worker at the same moment. A job method decorated with
`exclusive_job(name)` first takes the transaction-scoped advisory lock `job:<name>`. It
holds that lock until the job's transaction ends, and skips the run, returning None, when
another worker already has it. The next tick runs as normal.

Apply it under the class's `ALWAYS_NEW` transactional wrapper, so the lock lives exactly as
long as the job's own transaction. The sweeps also claim each row they act on, so a run
from an admin endpoint that overlaps a scheduled one is still safe.
"""
from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, TypeVar

from kink import di

from main.appodus_utils.db.locks import try_advisory_xact_lock

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']

_JOB_LOCK = "job"
T = TypeVar("T")


def exclusive_job(name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[Optional[T]]]]:
    """Run the decorated job only while holding `job:<name>`; None when another worker has it."""
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            if not await try_advisory_xact_lock(f"{_JOB_LOCK}:{name}"):
                logger.debug("Job {} skipped: another worker is running it", name)
                return None
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
