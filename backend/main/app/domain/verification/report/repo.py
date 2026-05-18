"""Report domain repositories — S35/S36."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import func, select

from main.app.domain.verification.report.models import (
    CreateReportVersionDto,
    CreateReportViewDto,
    ReportVersion,
    ReportView,
    UpdateReportVersionDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context
from sqlalchemy.ext.asyncio import AsyncSession


@inject
class ReportViewRepo(GenericRepo[ReportView, CreateReportViewDto, None, None, None]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReportView] = ReportView,
        query_dto=None,
    ) -> None:
        super().__init__(db, model, query_dto)
        self.db = db

    async def count_unacknowledged_for_customer(
        self, customer_id: str, completed_vids: List[str]
    ) -> int:
        """Return how many of the given completed VIDs have no ReportView for this customer."""
        if not completed_vids:
            return 0
        stmt = (
            select(func.count(func.distinct(ReportView.vid)))
            .where(
                ReportView.customer_id == customer_id,
                ReportView.deleted.is_(False),
                ReportView.vid.in_(completed_vids),
            )
        )
        result = await self._session.execute(stmt)
        acknowledged_count: int = result.scalar() or 0
        return len(completed_vids) - acknowledged_count

    async def get_for_customer(self, vid: str, customer_id: str) -> Optional[ReportView]:
        session = self._session
        result = await session.execute(
            select(ReportView)
            .where(
                ReportView.vid == vid,
                ReportView.customer_id == customer_id,
                ReportView.deleted.is_(False),
            )
            .limit(1)
        )
        return result.scalars().first()


@inject
class ReportVersionRepo(
    GenericRepo[ReportVersion, CreateReportVersionDto, UpdateReportVersionDto, None, None]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReportVersion] = ReportVersion,
        query_dto=None,
    ) -> None:
        super().__init__(db, model, query_dto)
        self.db = db

    async def current_for_vid(self, vid: str) -> Optional[ReportVersion]:
        session = self._session
        result = await session.execute(
            select(ReportVersion)
            .where(
                ReportVersion.vid == vid,
                ReportVersion.is_superseded.is_(False),
                ReportVersion.deleted.is_(False),
            )
            .order_by(ReportVersion.date_created.desc())
            .limit(1)
        )
        return result.scalars().first()
