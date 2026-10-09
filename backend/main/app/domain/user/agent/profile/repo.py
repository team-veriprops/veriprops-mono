from typing import List, Optional, Type

from kink import inject
from sqlalchemy import Uuid, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.profile.models import (
    AgentProfile,
    CreateAgentProfileDto,
    QueryAgentProfileDto,
    SearchAgentProfileDto,
    UpdateAgentProfileDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.search import contains_text


# The agent approval queue: the columns a client may sort by, and the order without one.
APPLICATION_SORTABLE = frozenset({"status", "submitted_at"})
APPLICATION_DEFAULT_ORDER = "submittedAt desc"


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
        self, status: Optional[str], offset: int, limit: int, query: Optional[str] = None,
        order_by: Optional[str] = None,
    ) -> tuple[List[AgentProfile], int, str]:
        """Applications in the client's *order_by* (newest submission first without one), plus the sort applied."""
        conditions = [AgentProfile.deleted.is_(False)]
        if status:
            conditions.append(AgentProfile.status == status)
        base = select(AgentProfile).where(*conditions)
        if query and query.strip():
            # Applicant name/email live on the User; join (application-level, no FK) to search them.
            # user_id is stored as str(user.id); cast it back to UUID to match the native User.id
            # PK (a bare `User.id == AgentProfile.user_id` raises uuid = varchar on Postgres).
            from main.app.domain.user.models import User
            base = base.join(User, User.id == cast(AgentProfile.user_id, Uuid)).where(
                contains_text(query, User.first_name, User.last_name, User.email)
            )
        applied, order = self._db_utils.client_order_by(order_by, APPLICATION_SORTABLE, APPLICATION_DEFAULT_ORDER)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (await self._session.execute(base.order_by(*order).offset(offset).limit(limit))).scalars().all()
        return list(rows), total or 0, applied
