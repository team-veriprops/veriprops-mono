from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.task.evidence.models import (
    CreateEvidenceItemDto,
    EvidenceItem,
    QueryEvidenceItemDto,
    SearchEvidenceItemDto,
    UpdateEvidenceItemDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class EvidenceItemRepo(
    GenericRepo[
        EvidenceItem,
        CreateEvidenceItemDto,
        UpdateEvidenceItemDto,
        QueryEvidenceItemDto,
        SearchEvidenceItemDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[EvidenceItem] = EvidenceItem,
        query_dto: Type[QueryEvidenceItemDto] = QueryEvidenceItemDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_task(self, task_id: str) -> List[EvidenceItem]:
        stmt = (
            select(EvidenceItem)
            .where(EvidenceItem.deleted.is_(False), EvidenceItem.task_id == task_id)
            .order_by(EvidenceItem.date_created.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_task(self, task_id: str) -> int:
        from sqlalchemy import func, select
        stmt = select(func.count(EvidenceItem.id)).where(
            EvidenceItem.deleted.is_(False),
            EvidenceItem.task_id == task_id,
        )
        return await self._session.scalar(stmt) or 0

    async def count_gps_for_task(self, task_id: str) -> int:
        from sqlalchemy import func, select
        stmt = select(func.count(EvidenceItem.id)).where(
            EvidenceItem.deleted.is_(False),
            EvidenceItem.task_id == task_id,
            EvidenceItem.gps_lat.is_not(None),
            EvidenceItem.gps_lng.is_not(None),
        )
        return await self._session.scalar(stmt) or 0
