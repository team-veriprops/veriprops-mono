"""Conflict flag repository (S29)."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.conflict.models import (
    ConflictFlag,
    ConflictStatus,
    CreateConflictFlagDto,
    QueryConflictFlagDto,
    SearchConflictFlagDto,
    UpdateConflictFlagDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ConflictFlagRepo(
    GenericRepo[
        ConflictFlag,
        CreateConflictFlagDto,
        UpdateConflictFlagDto,
        QueryConflictFlagDto,
        SearchConflictFlagDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ConflictFlag] = ConflictFlag,
        query_dto: Type[QueryConflictFlagDto] = QueryConflictFlagDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_verification(self, verification_id: str) -> List[ConflictFlag]:
        stmt = (
            select(ConflictFlag)
            .where(
                ConflictFlag.deleted.is_(False),
                ConflictFlag.verification_id == verification_id,
            )
            .order_by(ConflictFlag.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_open(self, verification_id: str) -> bool:
        stmt = select(ConflictFlag).where(
            ConflictFlag.deleted.is_(False),
            ConflictFlag.verification_id == verification_id,
            ConflictFlag.status == ConflictStatus.OPEN.value,
        ).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_id(self, flag_id: str) -> Optional[ConflictFlag]:
        stmt = select(ConflictFlag).where(
            ConflictFlag.deleted.is_(False),
            ConflictFlag.id == flag_id,
        ).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
