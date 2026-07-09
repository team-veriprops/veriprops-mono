"""Report acknowledgement data access."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.report.acknowledgement.models import (
    CreateReportAcknowledgementDto,
    QueryReportAcknowledgementDto,
    ReportAcknowledgement,
    SearchReportAcknowledgementDto,
    UpdateReportAcknowledgementDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ReportAcknowledgementRepo(
    GenericRepo[
        ReportAcknowledgement,
        CreateReportAcknowledgementDto,
        UpdateReportAcknowledgementDto,
        QueryReportAcknowledgementDto,
        SearchReportAcknowledgementDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReportAcknowledgement] = ReportAcknowledgement,
        query_dto: Type[QueryReportAcknowledgementDto] = QueryReportAcknowledgementDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for(
        self, customer_id: str, verification_id: str, report_version: int
    ) -> Optional[ReportAcknowledgement]:
        stmt = select(ReportAcknowledgement).where(
            ReportAcknowledgement.deleted.is_(False),
            ReportAcknowledgement.customer_id == customer_id,
            ReportAcknowledgement.verification_id == verification_id,
            ReportAcknowledgement.report_version == report_version,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
