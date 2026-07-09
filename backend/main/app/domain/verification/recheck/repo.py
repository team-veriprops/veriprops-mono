"""Re-check data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.recheck.models import (
    CreateRecheckDto,
    QueryRecheckDto,
    RecheckRequest,
    RecheckStatus,
    SearchRecheckDto,
    UpdateRecheckDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class RecheckRepo(
    GenericRepo[RecheckRequest, CreateRecheckDto, UpdateRecheckDto, QueryRecheckDto, SearchRecheckDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[RecheckRequest] = RecheckRequest,
        query_dto: Type[QueryRecheckDto] = QueryRecheckDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_payment(self, payment_id: str) -> Optional[RecheckRequest]:
        stmt = select(RecheckRequest).where(
            RecheckRequest.deleted.is_(False), RecheckRequest.payment_id == payment_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[RecheckRequest]:
        stmt = (
            select(RecheckRequest)
            .where(RecheckRequest.deleted.is_(False), RecheckRequest.verification_id == verification_id)
            .order_by(desc(RecheckRequest.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_pending(self, offset: int = 0, limit: int = 10):
        from sqlalchemy import func
        base = select(RecheckRequest).where(
            RecheckRequest.deleted.is_(False),
            RecheckRequest.status == RecheckStatus.PENDING.value,
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(RecheckRequest.date_created)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)
