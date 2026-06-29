"""IdempotencyKey data access (extends GenericRepo)."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.idempotency.models import (
    CreateIdempotencyKeyDto,
    IdempotencyKey,
    QueryIdempotencyKeyDto,
    UpdateIdempotencyKeyDto,
)
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

    async def get_by_key(self, key: str) -> Optional[IdempotencyKey]:
        """Return the (non-soft-deleted) row for ``key``, or None."""
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.deleted.is_(False),
            IdempotencyKey.key == key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
