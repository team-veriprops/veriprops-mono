"""Report domain repositories — S35/S36."""
from __future__ import annotations

from typing import Optional

from kink import inject
from sqlalchemy import select

from main.app.domain.verification.report.models import (
    CreateReportVersionDto,
    CreateReportViewDto,
    ReportVersion,
    ReportView,
    UpdateReportVersionDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class ReportViewRepo(GenericRepo[ReportView, CreateReportViewDto, None, None, None]):
    def __init__(self) -> None:
        super().__init__(ReportView)

    async def get_for_customer(self, vid: str, customer_id: str) -> Optional[ReportView]:
        session = get_db_session_from_context()
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
    def __init__(self) -> None:
        super().__init__(ReportVersion)

    async def current_for_vid(self, vid: str) -> Optional[ReportVersion]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(ReportVersion)
            .where(
                ReportVersion.vid == vid,
                ReportVersion.is_superseded.is_(False),
                ReportVersion.deleted.is_(False),
            )
            .order_by(ReportVersion.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()
