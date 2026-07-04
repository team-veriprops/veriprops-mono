"""Report data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.state.status import ReportState
from main.app.domain.verification.report.models import (
    CreateReportDto,
    QueryReportDto,
    Report,
    SearchReportDto,
    UpdateReportDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ReportRepo(
    GenericRepo[Report, CreateReportDto, UpdateReportDto, QueryReportDto, SearchReportDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Report] = Report,
        query_dto: Type[QueryReportDto] = QueryReportDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_verification(self, verification_id: str) -> List[Report]:
        stmt = (
            select(Report)
            .where(Report.deleted.is_(False), Report.verification_id == verification_id)
            .order_by(desc(Report.report_version))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_released(self, verification_id: str) -> Optional[Report]:
        stmt = select(Report).where(
            Report.deleted.is_(False),
            Report.verification_id == verification_id,
            Report.state == ReportState.RELEASED.value,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def latest_version(self, verification_id: str) -> int:
        reports = await self.list_for_verification(verification_id)
        return reports[0].report_version if reports else 0
