"""Report acknowledgement service (PRD §10.1) — the access-gate record."""
from __future__ import annotations

from kink import inject

from main.app.domain.verification.report.acknowledgement.models import (
    CreateReportAcknowledgementDto,
    ReportAcknowledgement,
)
from main.app.domain.verification.report.acknowledgement.repo import ReportAcknowledgementRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReportAcknowledgementService:
    def __init__(self, acknowledgement_repo: ReportAcknowledgementRepo):
        self._acknowledgement_repo = acknowledgement_repo

    async def is_acknowledged(
        self, customer_id: str, verification_id: str, report_version: int
    ) -> bool:
        return await self._acknowledgement_repo.get_for(customer_id, verification_id, report_version) is not None

    async def acknowledge(
        self, *, customer_id: str, verification_id: str, report_id: str, report_version: int
    ) -> ReportAcknowledgement:
        """Idempotently record the customer's acceptance of this report version's gate."""
        existing = await self._acknowledgement_repo.get_for(customer_id, verification_id, report_version)
        if existing is not None:
            return existing
        return await self._acknowledgement_repo.create_return_model(CreateReportAcknowledgementDto(
            verification_id=verification_id,
            report_id=report_id,
            report_version=report_version,
            customer_id=customer_id,
            acknowledged_at=Utils.datetime_now(),
        ))
