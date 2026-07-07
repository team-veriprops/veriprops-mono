from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, func, or_, select
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

    async def list_by_status(self, status: str) -> List[AgentProfile]:
        """All agent profiles in a status — feeds the reputation ranking (§16.1)."""
        stmt = select(AgentProfile).where(
            AgentProfile.deleted.is_(False),
            AgentProfile.status == status,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status(self, status: str) -> int:
        """Agent profiles/applications in a given status (admin dashboard §6)."""
        stmt = select(func.count()).select_from(AgentProfile).where(
            AgentProfile.deleted.is_(False),
            AgentProfile.status == status,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_available(self, approved_status: str, availability: str) -> int:
        """Approved agents currently signalling the given availability (Mission Control §18.1)."""
        stmt = select(func.count()).select_from(AgentProfile).where(
            AgentProfile.deleted.is_(False),
            AgentProfile.status == approved_status,
            AgentProfile.availability == availability,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def page_applications(
        self, status: Optional[str], offset: int, limit: int, query: Optional[str] = None
    ) -> tuple[List[AgentProfile], int]:
        conditions = [AgentProfile.deleted.is_(False)]
        if status:
            conditions.append(AgentProfile.status == status)
        base = select(AgentProfile).where(*conditions)
        if query and query.strip():
            # Applicant name/email live on the User; join (application-level, no FK) to search them.
            from main.app.domain.user.models import User
            like = f"%{query.strip()}%"
            base = base.join(User, User.id == AgentProfile.user_id).where(
                or_(
                    User.first_name.ilike(like),
                    User.last_name.ilike(like),
                    User.email.ilike(like),
                )
            )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(AgentProfile.submitted_at)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0
