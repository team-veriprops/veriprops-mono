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
from main.app.core.state.status import ReportRevisionKind, ReportState
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


def _next_version_label(prior_label: Optional[str], kind: ReportRevisionKind) -> str:
    """Compute the semantic version label from the prior label + revision kind (§10.1/§14, D29).

    INITIAL → "1.0". ADMIN_REVISION → a minor bump (1.0 → 1.1). RECHECK / TIER_UPGRADE →
    a new major (1.0 → 2.0 → 3.0). Prior versions are already SUPERSEDED by the caller.
    """
    if prior_label is None or kind == ReportRevisionKind.INITIAL:
        return "1.0"
    try:
        major, minor = (int(p) for p in prior_label.split(".", 1))
    except (ValueError, AttributeError):
        major, minor = 1, 0
    if kind == ReportRevisionKind.ADMIN_REVISION:
        return f"{major}.{minor + 1}"
    return f"{major + 1}.0"  # RECHECK / TIER_UPGRADE


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReportService:
    def __init__(self, report_repo: ReportRepo, audit_service: AuditLogService):
        self._report_repo = report_repo
        self._audit = audit_service

    async def release(
        self,
        *,
        verification_id: str,
        findings: Dict[str, Any],
        composite_trust_score: int,
        released_by: str,
        reason: Optional[str] = None,
        revision_kind: ReportRevisionKind = ReportRevisionKind.INITIAL,
    ) -> Report:
        """Release a new report version (§8.6). Any live RELEASED report is superseded first.
        ``revision_kind`` (§14) tags why the version was produced and drives the semantic
        version label (v1.0 → v2.0 re-check → v3.0 tier upgrade)."""
        existing = await self._report_repo.get_released(verification_id)
        prior_label = existing.version_label if existing is not None else None
        if existing is not None:
            report_state_machine.assert_can_transition(
                existing.state, ReportState.SUPERSEDED.value, resource="Report"
            )
            await self._report_repo.update(existing.id, UpdateReportDto(state=ReportState.SUPERSEDED.value))
            await self._set_superseded_at(existing.id)

        next_version = await self._report_repo.latest_version(verification_id) + 1
        report = await self._report_repo.create_return_model(CreateReportDto(
            verification_id=verification_id,
            report_version=next_version,
            version_label=_next_version_label(prior_label, revision_kind),
            revision_kind=revision_kind,
            state=ReportState.RELEASED,
            composite_trust_score=composite_trust_score,
            findings=findings,
            release_reason=reason,
            released_by=released_by,
        ))
        # Set the timestamp on the attached row and return it directly — re-fetching a row
        # created in this same (uncommitted) transaction can miss it.
        report.released_at = Utils.datetime_now()
        self._audit.schedule(
            action=AuditActionType.REPORT_RELEASED,
            resource_type="report", resource_id=report.id, actor_id=released_by,
            details={"verification_id": verification_id, "version": next_version,
                     "trust_score": composite_trust_score, "reason": reason},
        )
        return report

    async def supersede_current(self, verification_id: str, actor_id: str) -> Optional[Report]:
        """Move the live RELEASED report to SUPERSEDED (e.g. on reopen, §8.6). The report
        no longer reflects the verification once a task is reopened."""
        existing = await self._report_repo.get_released(verification_id)
        if existing is None:
            return None
        report_state_machine.assert_can_transition(
            existing.state, ReportState.SUPERSEDED.value, resource="Report"
        )
        await self._report_repo.update(existing.id, UpdateReportDto(state=ReportState.SUPERSEDED.value))
        await self._set_superseded_at(existing.id)
        self._audit.schedule(
            action=AuditActionType.REPORT_RELEASED,
            resource_type="report", resource_id=existing.id, actor_id=actor_id,
            from_state=ReportState.RELEASED.value, to_state=ReportState.SUPERSEDED.value,
            details={"event": "superseded_on_reopen", "verification_id": verification_id},
        )
        return await self._report_repo.get_model(existing.id)

    async def list_for_verification(self, verification_id: str) -> List[Report]:
        return await self._report_repo.list_for_verification(verification_id)

    async def get_released(self, verification_id: str) -> Optional[Report]:
        return await self._report_repo.get_released(verification_id)

    async def _set_released_at(self, report_id: str) -> None:
        report = await self._report_repo.get_model(report_id)
        report.released_at = Utils.datetime_now()

    async def _set_superseded_at(self, report_id: str) -> None:
        report = await self._report_repo.get_model(report_id)
        report.superseded_at = Utils.datetime_now()
