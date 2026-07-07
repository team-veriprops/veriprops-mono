"""Commission data access."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.commission.models import (
    Commission,
    CommissionStatus,
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

    async def get_live_for_task(
        self, verification_id: str, task_id: str
    ) -> Optional[Commission]:
        """A non-reversed commission already accrued for this task — the double-accrual
        guard on a re-release (§S18 follow-up). REVERSED rows don't block a fresh accrual."""
        stmt = select(Commission).where(
            Commission.deleted.is_(False),
            Commission.verification_id == verification_id,
            Commission.task_id == task_id,
            Commission.status != CommissionStatus.REVERSED.value,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_agent(self, agent_id: str) -> List[Commission]:
        stmt = select(Commission).where(
            Commission.deleted.is_(False), Commission.agent_id == agent_id
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_for_agent(
        self, agent_id: str, page: int, page_size: int
    ) -> Tuple[List[Commission], int]:
        base = select(Commission).where(
            Commission.deleted.is_(False), Commission.agent_id == agent_id
        )
        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = base.order_by(Commission.date_created.desc()).offset(page * page_size).limit(page_size)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total

    async def list_clearing_due(self, now: datetime) -> List[Commission]:
        """CLEARING commissions whose bulk-clearance date has passed (sweep pass 1)."""
        stmt = select(Commission).where(
            Commission.deleted.is_(False),
            Commission.status == CommissionStatus.CLEARING.value,
            Commission.clearing_until.is_not(None),
            Commission.clearing_until <= now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_reserve_due(self, now: datetime) -> List[Commission]:
        """AVAILABLE commissions with an unreleased reserve past its window (sweep pass 2)."""
        stmt = select(Commission).where(
            Commission.deleted.is_(False),
            Commission.status == CommissionStatus.AVAILABLE.value,
            Commission.reserve_amount_minor > 0,
            Commission.reserve_released_at.is_(None),
            Commission.reserve_until.is_not(None),
            Commission.reserve_until <= now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status(self) -> dict:
        """status → count over all commissions (Finance panel §18.1)."""
        from sqlalchemy import func, select
        stmt = select(Commission.status, func.count()).where(
            Commission.deleted.is_(False)
        ).group_by(Commission.status)
        return {s: int(c) for s, c in (await self._session.execute(stmt)).all()}
