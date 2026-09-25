"""IdempotencyKey data access (extends GenericRepo)."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.idempotency.models import (
    CreateIdempotencyKeyDto,
    IdempotencyKey,
    QueryIdempotencyKeyDto,
    UpdateIdempotencyKeyDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo


@inject
class IdempotencyKeyRepo(
    GenericRepo[
        IdempotencyKey,
        CreateIdempotencyKeyDto,
        UpdateIdempotencyKeyDto,
        QueryIdempotencyKeyDto,
        QueryIdempotencyKeyDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[IdempotencyKey] = IdempotencyKey,
        query_dto: Type[QueryIdempotencyKeyDto] = QueryIdempotencyKeyDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_key(self, key: str, scope: str) -> Optional[IdempotencyKey]:
        """The live row for ``key`` in ``scope``, or None. Keys are unique per scope."""
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.deleted.is_(False),
            IdempotencyKey.key == key,
            IdempotencyKey.scope == scope,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def retire_expired(self, key: str, scope: str) -> None:
        """Soft-delete ``key`` in ``scope`` if it has expired, freeing it for a new reservation.

        A statement, so the retirement is visible to the reservation insert that follows in
        the same transaction (the session does not autoflush).
        """
        now = Utils.datetime_now()
        await self._session.execute(
            update(IdempotencyKey)
            .where(
                IdempotencyKey.key == key,
                IdempotencyKey.scope == scope,
                IdempotencyKey.deleted.is_(False),
                IdempotencyKey.expires_at <= now,
            )
            .values(deleted=True, date_deleted=now)
        )
