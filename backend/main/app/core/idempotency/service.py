"""IdempotencyService — reusable idempotency primitive (PRD §4.6).

Two usage shapes:

- **Entity creation / payment initiation** (client idempotency key):
  ``outcome = await svc.begin_or_replay(key, scope, request_hash)``. If
  ``outcome.is_replay`` the caller returns the stored snapshot/resource without
  repeating the side effect; otherwise the caller performs the work and calls
  ``svc.complete(key, resource_id, response_snapshot)``.

- **Gateway webhooks** (event id as key): ``if not await svc.claim(event_id, scope):
  return`` — the first delivery claims the event; replays are dropped.

State changes here are written through ``@transactional`` so they commit with the
caller's enclosing transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.idempotency.models import (
    CreateIdempotencyKeyDto,
    IdempotencyStatus,
    UpdateIdempotencyKeyDto,
)
from main.app.core.idempotency.repo import IdempotencyKeyRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceConflictException,
    ResourceNotFoundException,
)

@dataclass(frozen=True)
class IdempotencyOutcome:
    """Result of :meth:`IdempotencyService.begin_or_replay`."""

    is_replay: bool
    resource_id: Optional[str] = None
    response_snapshot: Optional[Dict[str, Any]] = None


@inject
@decorate_all_methods(transactional(), exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude_startswith=["_"])
class IdempotencyService:
    def __init__(self, idempotency_repo: IdempotencyKeyRepo):
        self._idempotency_repo = idempotency_repo

    async def begin_or_replay(
        self,
        key: str,
        scope: str,
        request_hash: Optional[str] = None,
        ttl_hours: Optional[int] = None,
    ) -> IdempotencyOutcome:
        """Reserve ``key`` for ``scope`` or signal a replay of a prior call.

        Raises ``ResourceConflictException`` if the same key is reused with a
        different ``request_hash`` (a client bug or collision — never silently
        served the wrong response).
        """
        existing = await self._idempotency_repo.get_by_key(key)
        if existing is not None:
            if (
                request_hash is not None
                and existing.request_hash is not None
                and existing.request_hash != request_hash
            ):
                raise ResourceConflictException(
                    resource="IdempotencyKey",
                    message=f"Idempotency key {key!r} reused with a different request payload",
                )
            return IdempotencyOutcome(
                is_replay=True,
                resource_id=existing.resource_id,
                response_snapshot=existing.response_snapshot,
            )

        await self._idempotency_repo.create_return_model(
            CreateIdempotencyKeyDto(
                key=key,
                scope=scope,
                status=IdempotencyStatus.PENDING,
                request_hash=request_hash,
                expires_at=Utils.datetime_now() + timedelta(
                    hours=ttl_hours if ttl_hours is not None else settings.IDEMPOTENCY_KEY_TTL_HOURS
                ),
            )
        )
        # The session runs with autoflush=False, so flush the reservation now — otherwise the
        # matching `complete(key, ...)` later in the same transaction can't see this row via
        # get_by_key and raises "unknown idempotency key" (breaks every idempotent create).
        await get_db_session_from_context().flush()
        return IdempotencyOutcome(is_replay=False)

    async def complete(
        self,
        key: str,
        resource_id: Optional[str] = None,
        response_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a reserved key COMPLETED and store its replayable result."""
        existing = await self._idempotency_repo.get_by_key(key)
        if existing is None:
            raise ResourceNotFoundException(
                resource="IdempotencyKey",
                message=f"Cannot complete unknown idempotency key {key!r}",
            )
        await self._idempotency_repo.update_return_model(
            existing.id,
            UpdateIdempotencyKeyDto(
                status=IdempotencyStatus.COMPLETED,
                resource_id=resource_id,
                response_snapshot=response_snapshot,
            ),
        )

    async def claim(
        self,
        key: str,
        scope: str,
        ttl_hours: Optional[int] = None,
    ) -> bool:
        """One-shot dedup for webhooks: True if newly claimed, False if already seen."""
        existing = await self._idempotency_repo.get_by_key(key)
        if existing is not None:
            return False
        await self._idempotency_repo.create_return_model(
            CreateIdempotencyKeyDto(
                key=key,
                scope=scope,
                status=IdempotencyStatus.COMPLETED,
                expires_at=Utils.datetime_now() + timedelta(
                    hours=ttl_hours if ttl_hours is not None else settings.IDEMPOTENCY_KEY_TTL_HOURS
                ),
            )
        )
        return True
