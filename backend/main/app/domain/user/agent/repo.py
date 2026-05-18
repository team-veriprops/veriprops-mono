from datetime import timedelta
from typing import Optional, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.models import (
    AgentApplication,
    AgentMetricsDto,
    AgentQualityScore,
    AvailabilityStatus,
    CreateAgentApplicationDto,
    CreateAgentQualityScoreDto,
    QueryAgentApplicationDto,
    QueryAgentQualityScoreDto,
    SearchAgentApplicationDto,
    SearchAgentQualityScoreDto,
    UpdateAgentApplicationDto,
    UpdateAgentQualityScoreDto,
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


@inject
class AgentQualityScoreRepo(
    GenericRepo[
        AgentQualityScore,
        CreateAgentQualityScoreDto,
        UpdateAgentQualityScoreDto,
        QueryAgentQualityScoreDto,
        SearchAgentQualityScoreDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentQualityScore] = AgentQualityScore,
        query_dto: Type[QueryAgentQualityScoreDto] = QueryAgentQualityScoreDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_task_id(self, task_id: str) -> Optional[AgentQualityScore]:
        stmt = (
            select(AgentQualityScore)
            .where(
                AgentQualityScore.deleted.is_(False),
                AgentQualityScore.task_id == task_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def compute_metrics(
        self,
        agent_id: str,
        sla_hours: int = 48,
    ) -> AgentMetricsDto:
        """Aggregate task history into AgentMetricsDto.

        Imports Task inline to avoid circular import between agent and task
        domain packages.
        """
        from main.app.domain.verification.task.models import Task, TaskStatus

        sla_delta = timedelta(hours=sla_hours)

        # All tasks ever touched by this agent (excluding soft-deleted)
        base_stmt = select(Task).where(
            Task.deleted.is_(False),
            Task.agent_id == agent_id,
        )
        result = await self._session.execute(base_stmt)
        tasks = result.scalars().all()

        if not tasks:
            return AgentMetricsDto(
                completion_rate=0.0,
                accuracy_score=0.0,
                timeliness_score=0.0,
                total_jobs=0,
            )

        terminal_accepted = {
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.SUBMITTED.value,
            TaskStatus.APPROVED.value,
        }
        accepted_tasks = [t for t in tasks if t.status in terminal_accepted]
        approved_tasks = [t for t in tasks if t.status == TaskStatus.APPROVED.value]

        completion_rate = (
            len(approved_tasks) / len(accepted_tasks) * 100
            if accepted_tasks else 0.0
        )

        # Quality scores (only exist for APPROVED tasks that admin has rated)
        scores_stmt = select(AgentQualityScore).where(
            AgentQualityScore.deleted.is_(False),
            AgentQualityScore.agent_id == agent_id,
        )
        scores_result = await self._session.execute(scores_stmt)
        scores = scores_result.scalars().all()
        accuracy_score = (
            sum(s.score for s in scores) / len(scores)
            if scores else 0.0
        )

        # Timeliness: submitted within SLA from accepted_at
        submitted = [
            t for t in tasks
            if t.status in (TaskStatus.SUBMITTED.value, TaskStatus.APPROVED.value)
            and t.accepted_at is not None
            and t.submitted_at is not None
        ]
        on_time = [
            t for t in submitted
            if (t.submitted_at - t.accepted_at) <= sla_delta
        ]
        timeliness_score = (
            len(on_time) / len(submitted) * 100
            if submitted else 0.0
        )

        active_since = min((t.date_created for t in tasks), default=None)

        accuracy_score_rounded = round(accuracy_score, 2)
        total = len(tasks)
        return AgentMetricsDto(
            completion_rate=round(completion_rate, 1),
            accuracy_score=accuracy_score_rounded,
            timeliness_score=round(timeliness_score, 1),
            total_jobs=total,
            active_since=active_since,
            is_top_agent=accuracy_score_rounded >= 4.5 and total >= 10,
        )
