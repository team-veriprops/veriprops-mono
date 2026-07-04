"""Task evidence data access."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.task.evidence.models import (
    CreateEvidenceDto,
    EvidenceItem,
    QueryEvidenceDto,
    SearchEvidenceDto,
    UpdateEvidenceDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class EvidenceRepo(
    GenericRepo[
        EvidenceItem,
        CreateEvidenceDto,
        UpdateEvidenceDto,
        QueryEvidenceDto,
        SearchEvidenceDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[EvidenceItem] = EvidenceItem,
        query_dto: Type[QueryEvidenceDto] = QueryEvidenceDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_task(self, task_id: str) -> List[EvidenceItem]:
        stmt = (
            select(EvidenceItem)
            .where(EvidenceItem.deleted.is_(False), EvidenceItem.task_id == task_id)
            .order_by(EvidenceItem.uploaded_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_verification(self, verification_id: str) -> List[EvidenceItem]:
        """All evidence across a verification's tasks, newest first (customer feed §9.4)."""
        stmt = (
            select(EvidenceItem)
            .where(
                EvidenceItem.deleted.is_(False),
                EvidenceItem.verification_id == verification_id,
            )
            .order_by(EvidenceItem.uploaded_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_for_task(self, task_id: str) -> int:
        return len(await self.list_for_task(task_id))
