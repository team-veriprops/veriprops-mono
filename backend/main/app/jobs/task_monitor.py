"""Background jobs: pool-timeout alert + no-show alert for tasks (S21).

Both jobs read thresholds from admin_config and publish SSE events to admins.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from kink import di

if TYPE_CHECKING:
    from loguru import Logger

from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional
from main.app.domain.admin_config.service import AdminConfigService
from main.app.domain.verification.task.repo import TaskRepo

logger: "Logger" = di["logger"]


@transactional(session_policy=TransactionSessionPolicy.FALLBACK_NEW)
async def check_task_pool_timeouts() -> None:
    """Alert admin when a task has been PENDING too long with no agent accepting."""
    try:

        config_svc: AdminConfigService = di[AdminConfigService]
        task_repo: TaskRepo = di[TaskRepo]

        hours = await config_svc.get_int("pool_timeout_hours", fallback=24)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
        async def _run():
            stale_tasks = await task_repo.list_pending_stale(cutoff)
            for task in stale_tasks:
                _fire_sse_alert(
                    "POOL_TIMEOUT",
                    task_id=str(task.id),
                    verification_id=task.verification_id,
                    role=task.role,
                    hours=hours,
                )

        await _run()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pool_timeout check failed: {}", exc)


@transactional(session_policy=TransactionSessionPolicy.FALLBACK_NEW)
async def check_task_no_show_timeouts() -> None:
    """Alert admin when an ACCEPTED task has no progress past the no-show window."""
    try:

        config_svc: AdminConfigService = di[AdminConfigService]
        task_repo: TaskRepo = di[TaskRepo]

        hours = await config_svc.get_int("no_show_timeout_hours", fallback=4)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
        async def _run():
            no_show_tasks = await task_repo.list_accepted_no_progress(cutoff)
            for task in no_show_tasks:
                _fire_sse_alert(
                    "NO_SHOW",
                    task_id=str(task.id),
                    verification_id=task.verification_id,
                    role=task.role,
                    agent_id=task.agent_id,
                    hours=hours,
                )

        await _run()
    except Exception as exc:  # noqa: BLE001
        logger.warning("no_show check failed: {}", exc)


def _fire_sse_alert(event_type: str, **payload) -> None:
    try:
        import asyncio
        from main.appodus_utils.db.redis_utils import RedisUtils
        redis: RedisUtils = di[RedisUtils]
        asyncio.ensure_future(
            redis.publish("admin:task_alerts", {"event": event_type, **payload})
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"SSE alert publish failed [{event_type}]: {exc}")
