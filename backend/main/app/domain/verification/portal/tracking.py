"""Customer tracking service — live progress view of a verification (S32)."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from kink import di, inject

from main.app.domain.verification.portal.models import (
    AssignedAgentDto,
    SlaDto,
    TrackingDto,
)
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.models import TaskRole, TaskStatus
from main.app.domain.verification.task.repo import TaskRepo
from main.app.domain.user.repo import UserRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
)

_STATUS_LABELS: Dict[str, str] = {
    "DRAFT": "Draft",
    "SUBMITTED": "Submitted",
    "PAYMENT_PENDING": "Payment Pending",
    "PAID": "Paid — Awaiting Assignment",
    "IN_PROGRESS": "In Progress",
    "UNDER_REVIEW": "Under Admin Review",
    "COMPLETED": "Completed",
    "DISPUTED": "Disputed",
    "CANCELLED": "Cancelled",
    "REFUNDED": "Refunded",
    "FAILED": "Verification Failed",
}

_STATUS_DETAILS: Dict[str, str] = {
    "PAYMENT_PENDING": "Your payment is being processed. This usually takes a few minutes. If this persists beyond 30 minutes, contact support with your Verification ID.",
    "PAID": "Payment confirmed. Our team is assigning agents to your verification. You'll be notified within 24 hours.",
    "IN_PROGRESS": "Agents are actively working on your verification. No action required from you right now.",
    "UNDER_REVIEW": "All field work is complete. Our team is reviewing the findings for quality and consistency. This is intentional — expect your report shortly.",
    "COMPLETED": "Your report is ready. You may view and download it now.",
    "DISPUTED": "Your dispute has been filed and is under review. Our team will respond within 5 business days.",
    "FAILED": "This verification could not be completed. Contact support for assistance.",
}

_STATUS_PROGRESS: Dict[str, int] = {
    "DRAFT": 0,
    "SUBMITTED": 5,
    "PAYMENT_PENDING": 10,
    "PAID": 20,
    "IN_PROGRESS": 50,
    "UNDER_REVIEW": 80,
    "COMPLETED": 100,
    "DISPUTED": 90,
    "CANCELLED": 0,
    "REFUNDED": 0,
    "FAILED": 0,
}

_SLA_TARGET_DAYS: Dict[str, int] = {
    "BASIC": 5,
    "STANDARD": 10,
    "PREMIUM": 15,
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TrackingService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: TaskRepo,
        user_repo: UserRepo,
    ):
        self._verification_repo = verification_repo
        self._task_repo = task_repo
        self._user_repo = user_repo

    async def get_tracking(self, vid: str, customer_id: str) -> TrackingDto:
        ver = await self._verification_repo.get_by_vid(vid)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        if ver.customer_id != customer_id:
            raise ForbiddenException(message="Access denied")

        tasks = await self._task_repo.list_for_verification(str(ver.id))
        assigned_agents = await self._build_agent_list(tasks)
        sla = self._build_sla(ver)

        property_address: Optional[str] = None
        try:
            from main.app.domain.verification.property.repo import PropertyRepo
            prop_repo: PropertyRepo = di[PropertyRepo]
            if ver.property_id:
                prop = await prop_repo.get(ver.property_id)
                if prop:
                    property_address = getattr(prop, "address_line", None)
        except Exception:
            pass

        return TrackingDto(
            verification_id=str(ver.id),
            vid=ver.vid,
            status=ver.status,
            status_label=_STATUS_LABELS.get(ver.status, ver.status),
            status_detail=_STATUS_DETAILS.get(ver.status, ""),
            progress_pct=_STATUS_PROGRESS.get(ver.status, 0),
            tier=ver.tier,
            property_address=property_address,
            assigned_agents=assigned_agents,
            sla=sla,
            trust_score=Decimal(str(ver.trust_score)) if ver.trust_score is not None else None,
        )

    async def _build_agent_list(self, tasks) -> List[AssignedAgentDto]:
        agents: List[AssignedAgentDto] = []
        seen_agent_ids: set = set()
        for task in tasks:
            if task.agent_id and task.agent_id not in seen_agent_ids:
                seen_agent_ids.add(task.agent_id)
                user = await self._user_repo.get(task.agent_id)
                if user:
                    agents.append(AssignedAgentDto(
                        role=task.role,
                        first_name=user.first_name or "Agent",
                        is_trusted=False,
                    ))
        return agents

    def _build_sla(self, ver) -> Optional[SlaDto]:
        started_at = ver.paid_at
        if started_at is None:
            return None
        target_days = _SLA_TARGET_DAYS.get(ver.tier, 10)
        now = datetime.now(timezone.utc)
        delta = now - started_at
        elapsed_days = math.floor(delta.total_seconds() / 86400)
        on_track = elapsed_days <= target_days
        return SlaDto(
            started_at=started_at,
            target_days=target_days,
            elapsed_days=elapsed_days,
            on_track=on_track,
        )
