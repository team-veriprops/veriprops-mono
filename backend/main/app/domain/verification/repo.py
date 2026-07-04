from datetime import date
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.models import (
    CreateVerificationDto,
    QueryVerificationDto,
    SearchVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class VerificationRepo(
    GenericRepo[
        Verification,
        CreateVerificationDto,
        UpdateVerificationDto,
        QueryVerificationDto,
        SearchVerificationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Verification] = Verification,
        query_dto: Type[QueryVerificationDto] = QueryVerificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_vid(self, vid: str) -> Optional[Verification]:
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.vid == vid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def page_admin(
        self,
        *,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        state_region: Optional[str] = None,
        due_before: Optional[date] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[List[Verification], int]:
        """Admin control-panel list (§6.1). SLA-health (on-track/at-risk/overdue) is
        computed in the service from ``sla_due_date``; the DB filters the coarse facets."""
        conditions = [Verification.deleted.is_(False)]
        if status:
            conditions.append(Verification.status == status)
        if tier:
            conditions.append(Verification.tier == tier)
        if due_before:
            conditions.append(Verification.sla_due_date.is_not(None))
            conditions.append(Verification.sla_due_date <= due_before)
        base = select(Verification).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(Verification.date_created.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)
