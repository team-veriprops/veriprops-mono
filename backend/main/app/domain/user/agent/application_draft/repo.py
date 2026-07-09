from typing import Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.application_draft.models import (
    AgentApplicationDraft,
    CreateAgentApplicationDraftDto,
    QueryAgentApplicationDraftDto,
    SearchAgentApplicationDraftDto,
    UpdateAgentApplicationDraftDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentApplicationDraftRepo(
    GenericRepo[
        AgentApplicationDraft,
        CreateAgentApplicationDraftDto,
        UpdateAgentApplicationDraftDto,
        QueryAgentApplicationDraftDto,
        SearchAgentApplicationDraftDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentApplicationDraft] = AgentApplicationDraft,
        query_dto: Type[QueryAgentApplicationDraftDto] = QueryAgentApplicationDraftDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_active_for_user(self, user_id: str) -> Optional[AgentApplicationDraft]:
        stmt = (
            select(AgentApplicationDraft)
            .where(
                AgentApplicationDraft.deleted.is_(False),
                AgentApplicationDraft.user_id == user_id,
            )
            .order_by(desc(AgentApplicationDraft.date_created))
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
