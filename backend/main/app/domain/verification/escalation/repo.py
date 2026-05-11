from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.escalation.models import (
    CreateEscalationDto,
    Escalation,
    QueryEscalationDto,
    SearchEscalationDto,
    UpdateEscalationDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class EscalationRepo(
    GenericRepo[
        Escalation,
        CreateEscalationDto,
        UpdateEscalationDto,
        QueryEscalationDto,
        SearchEscalationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Escalation] = Escalation,
        query_dto: Type[QueryEscalationDto] = QueryEscalationDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_task(self, task_id: str) -> List[Escalation]:
        stmt = (
            select(Escalation)
            .where(Escalation.deleted.is_(False), Escalation.task_id == task_id)
            .order_by(Escalation.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
