from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.coverage.models import (
    AgentCoverage,
    CreateAgentCoverageDto,
    QueryAgentCoverageDto,
    SearchAgentCoverageDto,
    UpdateAgentCoverageDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentCoverageRepo(
    GenericRepo[
        AgentCoverage,
        CreateAgentCoverageDto,
        UpdateAgentCoverageDto,
        QueryAgentCoverageDto,
        SearchAgentCoverageDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentCoverage] = AgentCoverage,
        query_dto: Type[QueryAgentCoverageDto] = QueryAgentCoverageDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[AgentCoverage]:
        stmt = select(AgentCoverage).where(
            AgentCoverage.deleted.is_(False),
            AgentCoverage.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
