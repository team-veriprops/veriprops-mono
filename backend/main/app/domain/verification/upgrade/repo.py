"""Tier-upgrade data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.upgrade.models import (
    CreateUpgradeDto,
    QueryUpgradeDto,
    SearchUpgradeDto,
    UpdateUpgradeDto,
    UpgradeRequest,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class UpgradeRepo(
    GenericRepo[UpgradeRequest, CreateUpgradeDto, UpdateUpgradeDto, QueryUpgradeDto, SearchUpgradeDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[UpgradeRequest] = UpgradeRequest,
        query_dto: Type[QueryUpgradeDto] = QueryUpgradeDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_key(self, idempotency_key: str) -> Optional[UpgradeRequest]:
        stmt = select(UpgradeRequest).where(
            UpgradeRequest.deleted.is_(False), UpgradeRequest.idempotency_key == idempotency_key
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_payment(self, payment_id: str) -> Optional[UpgradeRequest]:
        stmt = select(UpgradeRequest).where(
            UpgradeRequest.deleted.is_(False), UpgradeRequest.payment_id == payment_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[UpgradeRequest]:
        stmt = (
            select(UpgradeRequest)
            .where(UpgradeRequest.deleted.is_(False), UpgradeRequest.verification_id == verification_id)
            .order_by(desc(UpgradeRequest.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())
