"""Task repository — competitive pool queries + optimistic-lock claim."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.task.models import (
    CreateTaskAssignmentDto,
    CreateTaskDto,
    QueryTaskAssignmentDto,
    QueryTaskDto,
    SearchTaskAssignmentDto,
    SearchTaskDto,
    Task,
    TaskAssignment,
    TaskStatus,
    UpdateTaskAssignmentDto,
    UpdateTaskDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class TaskRepo(
    GenericRepo[
        Task,
        CreateTaskDto,
        UpdateTaskDto,
        QueryTaskDto,
        SearchTaskDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Task] = Task,
        query_dto: Type[QueryTaskDto] = QueryTaskDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_verification(self, verification_id: str) -> List[Task]:
        stmt = (
            select(Task)
            .where(Task.deleted.is_(False), Task.verification_id == verification_id)
            .order_by(Task.role)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_for_agent(
        self, role: str, state: Optional[str] = None, excluded_task_ids: Optional[List[str]] = None
    ) -> List[Task]:
        """Return PENDING tasks visible to an agent with a given role."""
        conditions = [
            Task.deleted.is_(False),
            Task.status == TaskStatus.PENDING.value,
            Task.role == role,
        ]
        if excluded_task_ids:
            conditions.append(Task.id.notin_(excluded_task_ids))
        stmt = select(Task).where(*conditions).order_by(Task.pool_released_at.asc().nullsfirst())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_agent(self, agent_id: str) -> List[Task]:
        active_statuses = [
            TaskStatus.ASSIGNED.value,
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
        ]
        stmt = (
            select(Task)
            .where(
                Task.deleted.is_(False),
                Task.agent_id == agent_id,
                Task.status.in_(active_statuses),
            )
            .order_by(Task.accepted_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_completed_for_agent(self, agent_id: str) -> List[Task]:
        terminal_statuses = [TaskStatus.SUBMITTED.value, TaskStatus.APPROVED.value]
        stmt = (
            select(Task)
            .where(
                Task.deleted.is_(False),
                Task.agent_id == agent_id,
                Task.status.in_(terminal_statuses),
            )
            .order_by(Task.submitted_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_for_agent(self, agent_id: str) -> int:
        active_statuses = [
            TaskStatus.ASSIGNED.value,
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
        ]
        stmt = select(func.count(Task.id)).where(
            Task.deleted.is_(False),
            Task.agent_id == agent_id,
            Task.status.in_(active_statuses),
        )
        return await self._session.scalar(stmt) or 0

    async def claim_task(self, task_id: str, agent_id: str) -> bool:
        """Atomic optimistic-lock accept — UPDATE WHERE status='PENDING'.

        Returns True if the claim succeeded (1 row updated), False if another
        agent already accepted (0 rows updated → caller should raise 409).
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(Task)
            .where(
                Task.id == task_id,
                Task.status == TaskStatus.PENDING.value,
                Task.deleted.is_(False),
            )
            .values(
                status=TaskStatus.ACCEPTED.value,
                agent_id=agent_id,
                accepted_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_task(self, task_id: str) -> Optional[Task]:
        stmt = (
            select(Task)
            .where(Task.deleted.is_(False), Task.id == task_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending_stale(self, older_than: datetime) -> List[Task]:
        """Tasks stuck PENDING past the pool timeout threshold."""
        stmt = select(Task).where(
            Task.deleted.is_(False),
            Task.status == TaskStatus.PENDING.value,
            Task.pool_released_at <= older_than,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_accepted_no_progress(self, older_than: datetime) -> List[Task]:
        """Tasks ACCEPTED but with no evidence uploaded past no-show threshold."""
        stmt = select(Task).where(
            Task.deleted.is_(False),
            Task.status == TaskStatus.ACCEPTED.value,
            Task.accepted_at <= older_than,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class TaskAssignmentRepo(
    GenericRepo[
        TaskAssignment,
        CreateTaskAssignmentDto,
        UpdateTaskAssignmentDto,
        QueryTaskAssignmentDto,
        SearchTaskAssignmentDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[TaskAssignment] = TaskAssignment,
        query_dto: Type[QueryTaskAssignmentDto] = QueryTaskAssignmentDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_task(self, task_id: str) -> List[TaskAssignment]:
        stmt = (
            select(TaskAssignment)
            .where(TaskAssignment.deleted.is_(False), TaskAssignment.task_id == task_id)
            .order_by(TaskAssignment.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
