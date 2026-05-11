"""Customer-facing evidence service — S34.

Lists all evidence items for a verification with role-tagging.
Never returns agent identity (uploader_id, last_name, email, phone).
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.verification.portal.models import CustomerEvidenceItemDto
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.evidence.repo import EvidenceItemRepo
from main.app.domain.verification.task.repo import TaskRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CustomerEvidenceService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: TaskRepo,
        evidence_repo: EvidenceItemRepo,
    ):
        self._verifications = verification_repo
        self._tasks = task_repo
        self._evidence = evidence_repo

    async def list_evidence(self, vid: str, customer_id: str) -> List[CustomerEvidenceItemDto]:
        ver = await self._verifications.get_by_vid(vid)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        if ver.customer_id != customer_id:
            raise ForbiddenException(message="Access denied")

        tasks = await self._tasks.list_for_verification(str(ver.id))
        task_role_map = {str(t.id): t.role for t in tasks}

        items: List[CustomerEvidenceItemDto] = []
        for task in tasks:
            evidence = await self._evidence.list_for_task(str(task.id))
            for ev in evidence:
                items.append(CustomerEvidenceItemDto(
                    id=str(ev.id),
                    evidence_type=ev.type,
                    file_url=ev.file_url,
                    gps_lat=ev.gps_lat,
                    gps_lng=ev.gps_lng,
                    captured_at=ev.captured_at,
                    agent_role=task_role_map.get(str(task.id), task.role),
                ))

        # Sort by captured_at ascending
        items.sort(key=lambda x: x.captured_at or "")
        return items
