"""Commission data access."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.commission.models import (
    Commission,
    CreateCommissionDto,
    QueryCommissionDto,
    SearchCommissionDto,
    UpdateCommissionDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class CommissionRepo(
    GenericRepo[
        Commission,
        CreateCommissionDto,
        UpdateCommissionDto,
        QueryCommissionDto,
        SearchCommissionDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Commission] = Commission,
        query_dto: Type[QueryCommissionDto] = QueryCommissionDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_verification(self, verification_id: str) -> List[Commission]:
        stmt = select(Commission).where(
            Commission.deleted.is_(False),
            Commission.verification_id == verification_id,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_verification_in_status(
        self, verification_id: str, statuses: List[str]
    ) -> List[Commission]:
        stmt = select(Commission).where(
            Commission.deleted.is_(False),
            Commission.verification_id == verification_id,
            Commission.status.in_(statuses),
        )
        return list((await self._session.execute(stmt)).scalars().all())
