from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.profile.models import (
    AgentProfile,
    CreateAgentProfileDto,
    QueryAgentProfileDto,
    SearchAgentProfileDto,
    UpdateAgentProfileDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentProfileRepo(
    GenericRepo[
        AgentProfile,
        CreateAgentProfileDto,
        UpdateAgentProfileDto,
        QueryAgentProfileDto,
        SearchAgentProfileDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentProfile] = AgentProfile,
        query_dto: Type[QueryAgentProfileDto] = QueryAgentProfileDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[AgentProfile]:
        stmt = select(AgentProfile).where(
            AgentProfile.deleted.is_(False),
            AgentProfile.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def page_applications(
        self, status: Optional[str], offset: int, limit: int
    ) -> tuple[List[AgentProfile], int]:
        conditions = [AgentProfile.deleted.is_(False)]
        if status:
            conditions.append(AgentProfile.status == status)
        base = select(AgentProfile).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(AgentProfile.submitted_at)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0
