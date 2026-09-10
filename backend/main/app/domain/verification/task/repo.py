"""Task data access — extends GenericRepo with the lifecycle-specific queries the
assignment, derivation, capacity, and timeout-sweep paths need."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.state.status import TaskState
from main.app.domain.verification.task.models import (
    CreateTaskDto,
    QueryTaskDto,
    SearchTaskDto,
    UpdateTaskDto,
    VerificationTask,
)
from main.appodus_utils.db.repo import GenericRepo

# States in which a task counts against an agent's active-task capacity (§6.5, §11.3).
_ACTIVE_STATES = (
    TaskState.ASSIGNED.value,
    TaskState.ACCEPTED.value,
    TaskState.IN_PROGRESS.value,
    TaskState.REJECTED.value,
)


@inject
class VerificationTaskRepo(
    GenericRepo[
        VerificationTask,
        CreateTaskDto,
        UpdateTaskDto,
        QueryTaskDto,
        SearchTaskDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[VerificationTask] = VerificationTask,
        query_dto: Type[QueryTaskDto] = QueryTaskDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_verification(self, verification_id: str) -> List[VerificationTask]:
        stmt = (
            select(VerificationTask)
            .where(
                VerificationTask.deleted.is_(False),
                VerificationTask.verification_id == verification_id,
            )
            .order_by(VerificationTask.date_created.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_role(self, verification_id: str, role: str) -> Optional[VerificationTask]:
        stmt = select(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.verification_id == verification_id,
            VerificationTask.role == role,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all_for_agent(self, agent_id: str) -> List[VerificationTask]:
        """Every task ever assigned to an agent — feeds the reputation metrics (§16.1)."""
        stmt = select(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.assigned_agent_id == agent_id,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_active_for_agent(self, agent_id: str) -> int:
        """Tasks that count against ``agent_max_active_tasks`` (§6.5)."""
        stmt = select(func.count()).select_from(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.assigned_agent_id == agent_id,
            VerificationTask.state.in_(_ACTIVE_STATES),
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_pool_pending(self) -> int:
        """Broadcast tasks sitting unclaimed in the open pool (admin dashboard §6.3)."""
        stmt = select(func.count()).select_from(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.in_pool.is_(True),
            VerificationTask.state == TaskState.PENDING.value,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_by_state_for_agent(self, agent_id: str) -> dict[str, int]:
        """state → count over an agent's assigned tasks (agent dashboard §12)."""
        stmt = (
            select(VerificationTask.state, func.count())
            .where(
                VerificationTask.deleted.is_(False),
                VerificationTask.assigned_agent_id == agent_id,
            )
            .group_by(VerificationTask.state)
        )
        rows = (await self._session.execute(stmt)).all()
        return {state: int(count) for state, count in rows}

    async def list_pool_expired(self, now: datetime) -> List[VerificationTask]:
        """Broadcast tasks still unclaimed past their pool timeout (§11.4 starvation)."""
        stmt = select(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.in_pool.is_(True),
            VerificationTask.state == TaskState.PENDING.value,
            VerificationTask.pool_expires_at.is_not(None),
            VerificationTask.pool_expires_at < now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_accept_deadline_expired(self, now: datetime) -> List[VerificationTask]:
        """Manually-assigned tasks the agent never accepted in time (§11.4 no-show)."""
        stmt = select(VerificationTask).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.state == TaskState.ASSIGNED.value,
            VerificationTask.accept_deadline_at.is_not(None),
            VerificationTask.accept_deadline_at < now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_for_agent(
        self, agent_id: str, states: Optional[List[str]], offset: int, limit: int
    ) -> tuple[List[VerificationTask], int]:
        conditions = [
            VerificationTask.deleted.is_(False),
            VerificationTask.assigned_agent_id == agent_id,
        ]
        if states:
            conditions.append(VerificationTask.state.in_(states))
        base = select(VerificationTask).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(VerificationTask.date_created.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    async def list_approved_since(self, cutoff: datetime) -> List[tuple]:
        """(approved_at, review_quality) for tasks approved since ``cutoff`` — the agent
        performance-trend series (§18.1 analytics, 6-month window)."""
        stmt = select(VerificationTask.approved_at, VerificationTask.review_quality).where(
            VerificationTask.deleted.is_(False),
            VerificationTask.approved_at.is_not(None),
            VerificationTask.approved_at >= cutoff,
        )
        return [(a, q) for a, q in (await self._session.execute(stmt)).all()]
