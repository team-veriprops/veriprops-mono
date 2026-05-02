from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.models import (
    AgentApplication,
    CreateAgentApplicationDto,
    QueryAgentApplicationDto,
    SearchAgentApplicationDto,
    UpdateAgentApplicationDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentApplicationRepo(
    GenericRepo[
        AgentApplication,
        CreateAgentApplicationDto,
        UpdateAgentApplicationDto,
        QueryAgentApplicationDto,
        SearchAgentApplicationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentApplication] = AgentApplication,
        query_dto: Type[QueryAgentApplicationDto] = QueryAgentApplicationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[AgentApplication]:
        stmt = (
            select(AgentApplication)
            .where(
                AgentApplication.deleted.is_(False),
                AgentApplication.user_id == user_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
