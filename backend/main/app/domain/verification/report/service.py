"""Report service (PRD §8.3, §8.6, §10).

Produces the versioned released report at admin release and supersedes prior versions.
Never auto-creates a report — the review service calls ``release`` explicitly as the
gate. Versioning: each release increments ``report_version`` and moves the previous
RELEASED report to SUPERSEDED via the report state machine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from kink import inject

from main.app.core.state.machine import report_state_machine
from main.app.core.state.status import ReportState
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.report.models import (
    CreateReportDto,
    Report,
    UpdateReportDto,
)
from main.app.domain.verification.report.repo import ReportRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReportService:
    def __init__(self, report_repo: ReportRepo, audit_service: AuditLogService):
        self._repo = report_repo
        self._audit = audit_service

    async def release(
        self,
        *,
        verification_id: str,
        findings: Dict[str, Any],
        composite_trust_score: int,
        released_by: str,
        reason: Optional[str] = None,
    ) -> Report:
        """Release a new report version (§8.6). Any live RELEASED report is superseded first."""
        existing = await self._repo.get_released(verification_id)
        if existing is not None:
            report_state_machine.assert_can_transition(
                existing.state, ReportState.SUPERSEDED.value, resource="Report"
            )
            await self._repo.update(existing.id, UpdateReportDto(state=ReportState.SUPERSEDED.value))
            await self._set_superseded_at(existing.id)

        next_version = await self._repo.latest_version(verification_id) + 1
        report = await self._repo.create_return_model(CreateReportDto(
            verification_id=verification_id,
            report_version=next_version,
            state=ReportState.RELEASED,
            composite_trust_score=composite_trust_score,
            findings=findings,
            release_reason=reason,
            released_by=released_by,
        ))
        await self._set_released_at(report.id)
        self._audit.schedule(
            action=AuditActionType.REPORT_RELEASED,
            resource_type="report", resource_id=report.id, actor_id=released_by,
            details={"verification_id": verification_id, "version": next_version,
                     "trust_score": composite_trust_score, "reason": reason},
        )
        return await self._repo.get_model(report.id)

    async def supersede_current(self, verification_id: str, actor_id: str) -> Optional[Report]:
        """Move the live RELEASED report to SUPERSEDED (e.g. on reopen, §8.6). The report
        no longer reflects the verification once a task is reopened."""
        existing = await self._repo.get_released(verification_id)
        if existing is None:
            return None
        report_state_machine.assert_can_transition(
            existing.state, ReportState.SUPERSEDED.value, resource="Report"
        )
        await self._repo.update(existing.id, UpdateReportDto(state=ReportState.SUPERSEDED.value))
        await self._set_superseded_at(existing.id)
        self._audit.schedule(
            action=AuditActionType.REPORT_RELEASED,
            resource_type="report", resource_id=existing.id, actor_id=actor_id,
            from_state=ReportState.RELEASED.value, to_state=ReportState.SUPERSEDED.value,
            details={"event": "superseded_on_reopen", "verification_id": verification_id},
        )
        return await self._repo.get_model(existing.id)

    async def list_for_verification(self, verification_id: str) -> List[Report]:
        return await self._repo.list_for_verification(verification_id)

    async def get_released(self, verification_id: str) -> Optional[Report]:
        return await self._repo.get_released(verification_id)

    async def _set_released_at(self, report_id: str) -> None:
        report = await self._repo.get_model(report_id)
        report.released_at = Utils.datetime_now()

    async def _set_superseded_at(self, report_id: str) -> None:
        report = await self._repo.get_model(report_id)
        report.superseded_at = Utils.datetime_now()
