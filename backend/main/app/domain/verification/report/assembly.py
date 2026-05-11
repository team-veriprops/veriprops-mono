"""Report assembly service — S35.

Assembles the full verification report from task payloads.
Tier-conditional sections: registry always; physical+boundary for STANDARD+;
legal opinion for PREMIUM only. Records first-view acknowledgement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from kink import inject

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.report.models import (
    CreateReportViewDto,
    ReportDto,
)
from main.app.domain.verification.report.repo import ReportVersionRepo, ReportViewRepo
from main.app.domain.verification.task.models import TaskRole
from main.app.domain.verification.task.repo import TaskRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReportAssemblyService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: TaskRepo,
        view_repo: ReportViewRepo,
        version_repo: ReportVersionRepo,
    ):
        self._verifications = verification_repo
        self._tasks = task_repo
        self._views = view_repo
        self._versions = version_repo

    async def assemble(self, vid: str, customer_id: str) -> ReportDto:
        ver = await self._verifications.get_by_vid(vid)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        if ver.customer_id != customer_id:
            raise ForbiddenException(message="Access denied")
        if ver.status != VerificationStatus.COMPLETED.value:
            raise ValidationException(message="Report is only available for completed verifications")

        tasks = await self._tasks.list_for_verification(str(ver.id))
        task_payloads: Dict[str, Any] = {}
        for task in tasks:
            if task.draft_payload:
                try:
                    task_payloads[task.role] = json.loads(task.draft_payload)
                except (json.JSONDecodeError, TypeError):
                    task_payloads[task.role] = {}

        tier = ver.tier.upper()
        registry = task_payloads.get(TaskRole.REGISTRY.value, {})
        field = task_payloads.get(TaskRole.FIELD.value, {})
        surveyor = task_payloads.get(TaskRole.SURVEYOR.value, {})
        lawyer = task_payloads.get(TaskRole.LAWYER.value, {})

        current_version = await self._versions.current_for_vid(vid)
        version_str = current_version.version_string if current_version else "v1.0"

        has_ack = await self.has_acknowledged(vid, customer_id)

        return ReportDto(
            vid=vid,
            version=version_str,
            tier=tier,
            completed_at=ver.completed_at,
            trust_score=Decimal(str(ver.trust_score)) if ver.trust_score is not None else None,
            executive_summary=self._build_executive_summary(tier, task_payloads),
            registry_findings=registry or None,
            physical_findings=field or None if tier in ("STANDARD", "PREMIUM") else None,
            boundary_findings=surveyor or None if tier in ("STANDARD", "PREMIUM") else None,
            legal_opinion=lawyer or None if tier == "PREMIUM" else None,
            risk_summary=self._build_risk_summary(task_payloads),
            has_acknowledged=has_ack,
        )

    async def record_acknowledgement(
        self, vid: str, customer_id: str, ip_address: Optional[str] = None,
    ) -> None:
        if await self.has_acknowledged(vid, customer_id):
            return  # Idempotent — second call is a no-op
        current_version = await self._versions.current_for_vid(vid)
        await self._views.create_return_model(
            CreateReportViewDto(
                vid=vid,
                customer_id=customer_id,
                acknowledged_at=datetime.now(timezone.utc),
                ip_address=ip_address,
                report_version=current_version.version_string if current_version else None,
            )
        )

    async def has_acknowledged(self, vid: str, customer_id: str) -> bool:
        row = await self._views.get_for_customer(vid, customer_id)
        return row is not None

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_executive_summary(tier: str, payloads: Dict[str, Any]) -> str:
        parts = []
        registry = payloads.get(TaskRole.REGISTRY.value, {})
        if registry.get("ownership_chain"):
            chain = registry["ownership_chain"]
            parts.append(f"Ownership chain verified with {len(chain)} record(s).")
        if registry.get("title_doc_assessment"):
            parts.append(f"Title document assessed as {registry['title_doc_assessment']}.")
        if tier in ("STANDARD", "PREMIUM"):
            field = payloads.get(TaskRole.FIELD.value, {})
            if field.get("occupancy_status"):
                parts.append(f"Property is {field['occupancy_status']}.")
        if tier == "PREMIUM":
            lawyer = payloads.get(TaskRole.LAWYER.value, {})
            if lawyer.get("document_authenticity"):
                parts.append(f"Legal opinion: document {lawyer['document_authenticity']}.")
        return " ".join(parts) or "Verification completed."

    @staticmethod
    def _build_risk_summary(payloads: Dict[str, Any]) -> str:
        risk_items = []
        field = payloads.get(TaskRole.FIELD.value, {})
        registry = payloads.get(TaskRole.REGISTRY.value, {})
        lawyer = payloads.get(TaskRole.LAWYER.value, {})
        if field.get("occupancy_status") == "VACANT" and registry.get("registered_occupancy") == "OCCUPIED":
            risk_items.append("Occupancy mismatch between field report and registry records.")
        if lawyer.get("document_authenticity") == "FORGED":
            risk_items.append("Title document assessed as potentially forged by legal review.")
        return " ".join(risk_items) or "No major risks identified."

    def build_template_context(self, report: ReportDto) -> Dict[str, Any]:
        return {
            "vid": report.vid,
            "version": report.version,
            "tier": report.tier,
            "completed_at": report.completed_at,
            "trust_score": float(report.trust_score) if report.trust_score is not None else None,
            "executive_summary": report.executive_summary,
            "registry_findings": report.registry_findings,
            "physical_findings": report.physical_findings,
            "boundary_findings": report.boundary_findings,
            "legal_opinion": report.legal_opinion,
            "risk_summary": report.risk_summary,
            "is_standard_plus": report.tier in ("STANDARD", "PREMIUM"),
            "is_premium": report.tier == "PREMIUM",
        }
