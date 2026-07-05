"""Dispute data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.dispute.models import (
    CreateDisputeDto,
    Dispute,
    DisputeStatus,
    QueryDisputeDto,
    SearchDisputeDto,
    UpdateDisputeDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class DisputeRepo(
    GenericRepo[Dispute, CreateDisputeDto, UpdateDisputeDto, QueryDisputeDto, SearchDisputeDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Dispute] = Dispute,
        query_dto: Type[QueryDisputeDto] = QueryDisputeDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_verification(self, verification_id: str) -> List[Dispute]:
        stmt = (
            select(Dispute)
            .where(Dispute.deleted.is_(False), Dispute.verification_id == verification_id)
            .order_by(desc(Dispute.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_open_for_agent(self, dispute_id: str, agent_id: str) -> Optional[Dispute]:
        stmt = select(Dispute).where(
            Dispute.deleted.is_(False), Dispute.id == dispute_id,
            Dispute.agent_id == agent_id, Dispute.status == DisputeStatus.OPEN.value,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def page_open(self, offset: int = 0, limit: int = 10):
        base = select(Dispute).where(
            Dispute.deleted.is_(False), Dispute.status == DisputeStatus.OPEN.value
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(Dispute.date_created)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)
