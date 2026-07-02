from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.credential.models import (
    AgentCredential,
    CreateAgentCredentialDto,
    QueryAgentCredentialDto,
    SearchAgentCredentialDto,
    UpdateAgentCredentialDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentCredentialRepo(
    GenericRepo[
        AgentCredential,
        CreateAgentCredentialDto,
        UpdateAgentCredentialDto,
        QueryAgentCredentialDto,
        SearchAgentCredentialDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentCredential] = AgentCredential,
        query_dto: Type[QueryAgentCredentialDto] = QueryAgentCredentialDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[AgentCredential]:
        stmt = select(AgentCredential).where(
            AgentCredential.deleted.is_(False),
            AgentCredential.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
