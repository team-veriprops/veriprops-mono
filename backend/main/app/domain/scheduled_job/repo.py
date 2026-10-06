"""Scheduled job run data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.scheduled_job.models import (
    CreateScheduledJobRunDto,
    QueryScheduledJobRunDto,
    ScheduledJobRun,
    SearchScheduledJobRunDto,
    UpdateScheduledJobRunDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ScheduledJobRunRepo(
    GenericRepo[
        ScheduledJobRun,
        CreateScheduledJobRunDto,
        UpdateScheduledJobRunDto,
        QueryScheduledJobRunDto,
        SearchScheduledJobRunDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ScheduledJobRun] = ScheduledJobRun,
        query_dto: Type[QueryScheduledJobRunDto] = QueryScheduledJobRunDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def claim_run(self, name: str, *, expected_last_run_at: Optional[datetime], at: datetime) -> bool:
        """Record a run starting *at*, only if the job's last run is still the one read.

        One conditional UPDATE: the due decision rested on *expected_last_run_at*, and a
        concurrent runner that already claimed this fire has moved it, so this one matches no
        row and loses. True when this caller won.
        """
        last_run_at = ScheduledJobRun.last_run_at
        stmt = (
            update(ScheduledJobRun)
            .where(
                ScheduledJobRun.deleted.is_(False),
                ScheduledJobRun.name == name,
                last_run_at.is_(None) if expected_last_run_at is None else last_run_at == expected_last_run_at,
            )
            .values(last_run_at=at, date_updated=at, version=ScheduledJobRun.version + 1)
            .returning(ScheduledJobRun.name)
        )
        return (await self._session.execute(stmt)).scalar() is not None
