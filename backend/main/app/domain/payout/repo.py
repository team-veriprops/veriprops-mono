"""Payout data access."""
from __future__ import annotations

from typing import List, Tuple, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payout.models import (
    CreatePayoutDto,
    Payout,
    QueryPayoutDto,
    SearchPayoutDto,
    UpdatePayoutDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PayoutRepo(
    GenericRepo[Payout, CreatePayoutDto, UpdatePayoutDto, QueryPayoutDto, SearchPayoutDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Payout] = Payout,
        query_dto: Type[QueryPayoutDto] = QueryPayoutDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_agent(self, agent_id: str) -> List[Payout]:
        stmt = select(Payout).where(Payout.deleted.is_(False), Payout.agent_id == agent_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_agent_in_status(self, agent_id: str, statuses: List[str]) -> List[Payout]:
        stmt = select(Payout).where(
            Payout.deleted.is_(False),
            Payout.agent_id == agent_id,
            Payout.status.in_(statuses),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_for_agent(
        self, agent_id: str, page: int, page_size: int
    ) -> Tuple[List[Payout], int]:
        return await self._page(page, page_size, agent_id=agent_id)

    async def page_all(
        self, page: int, page_size: int, status: str | None = None
    ) -> Tuple[List[Payout], int]:
        return await self._page(page, page_size, status=status)

    async def _page(
        self, page: int, page_size: int, agent_id: str | None = None, status: str | None = None
    ) -> Tuple[List[Payout], int]:
        conditions = [Payout.deleted.is_(False)]
        if agent_id:
            conditions.append(Payout.agent_id == agent_id)
        if status:
            conditions.append(Payout.status == status)
        base = select(Payout).where(*conditions)
        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = base.order_by(Payout.date_created.desc()).offset(page * page_size).limit(page_size)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total

    async def count_by_status(self) -> dict:
        """status → count over all payouts (Finance panel §18.1)."""
        stmt = select(Payout.status, func.count()).where(
            Payout.deleted.is_(False)
        ).group_by(Payout.status)
        return {s: int(c) for s, c in (await self._session.execute(stmt)).all()}
