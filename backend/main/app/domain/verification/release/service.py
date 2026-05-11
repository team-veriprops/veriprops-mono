"""Release service — admin releases report to customer or marks FAILED (S31).

release(): UNDER_REVIEW → COMPLETED (gated: all tasks APPROVED, no open conflicts)
fail():    UNDER_REVIEW → FAILED   (irreversible, reason required ≥50 chars)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.models import UpdateVerificationDto, VerificationStatus
from main.app.domain.verification.release.models import _MIN_FAIL_REASON_LENGTH, ReleaseDto
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.models import TaskStatus
from main.app.domain.verification.task.repo import TaskRepo
from main.app.state.machine import verification_state_machine
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReleaseService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: TaskRepo,
        audit: AuditLogService,
    ):
        self._verifications = verification_repo
        self._tasks = task_repo
        self._audit = audit

    async def release(self, vid: str, admin_id: str) -> ReleaseDto:
        """Transition UNDER_REVIEW → COMPLETED after passing all pre-checks."""
        ver = await self._get_under_review_or_raise(vid)

        # Pre-check 1: all tasks must be APPROVED
        tasks = await self._tasks.list_for_verification(str(ver.id))
        unapproved = [t for t in tasks if t.status != TaskStatus.APPROVED.value]
        if unapproved:
            roles = [t.role for t in unapproved]
            raise ValidationException(
                message=f"Cannot release: tasks not yet approved — {', '.join(roles)}"
            )

        # Pre-check 2: no open conflict flags
        if await self._has_open_conflicts(str(ver.id)):
            raise ValidationException(
                message="Cannot release: open conflict flags must be resolved first"
            )

        verification_state_machine.assert_can_transition(
            ver.status, VerificationStatus.COMPLETED.value, resource="Verification"
        )
        now = datetime.now(timezone.utc)
        await self._verifications.update(
            str(ver.id),
            UpdateVerificationDto(status=VerificationStatus.COMPLETED, completed_at=now),
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(ver.id),
            actor_id=admin_id,
            from_state=VerificationStatus.UNDER_REVIEW.value,
            to_state=VerificationStatus.COMPLETED.value,
            meta={"action": "RELEASE_REPORT"},
        )
        await self._publish(str(ver.id), "report_released")
        return ReleaseDto(
            verification_id=str(ver.id),
            vid=ver.vid,
            status=VerificationStatus.COMPLETED.value,
            completed_at=now.isoformat(),
        )

    async def fail_release(self, vid: str, admin_id: str, reason: str) -> ReleaseDto:
        """Irreversible UNDER_REVIEW → FAILED with mandatory reason (≥50 chars)."""
        if len(reason.strip()) < _MIN_FAIL_REASON_LENGTH:
            raise ValidationException(
                message=f"Reason must be at least {_MIN_FAIL_REASON_LENGTH} characters"
            )
        ver = await self._get_under_review_or_raise(vid)
        verification_state_machine.assert_can_transition(
            ver.status, VerificationStatus.FAILED.value, resource="Verification"
        )
        await self._verifications.update(
            str(ver.id),
            UpdateVerificationDto(status=VerificationStatus.FAILED),
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(ver.id),
            actor_id=admin_id,
            from_state=VerificationStatus.UNDER_REVIEW.value,
            to_state=VerificationStatus.FAILED.value,
            meta={"action": "FAIL_RELEASE", "reason": reason},
        )
        await self._publish(str(ver.id), "verification_failed")
        return ReleaseDto(
            verification_id=str(ver.id),
            vid=ver.vid,
            status=VerificationStatus.FAILED.value,
        )

    # ── helpers ───────────────────────────────────────────────────────

    async def _get_under_review_or_raise(self, vid: str):
        ver = await self._verifications.get_by_vid(vid)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        if ver.status != VerificationStatus.UNDER_REVIEW.value:
            raise ValidationException(
                message=f"Verification must be in UNDER_REVIEW status (current: {ver.status})"
            )
        return ver

    async def _has_open_conflicts(self, verification_id: str) -> bool:
        try:
            from main.app.domain.verification.conflict.service import ConflictService
            svc: ConflictService = di[ConflictService]
            return await svc.has_open_conflicts(verification_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Conflict check failed for {verification_id}: {exc}")
            return False

    async def _publish(self, verification_id: str, event: str) -> None:
        try:
            from main.appodus_utils.db.redis_utils import RedisUtils
            redis: RedisUtils = di[RedisUtils]
            await redis.publish(
                f"verifications:{verification_id}",
                {"event": event, "verification_id": verification_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE publish failed ({event}): {exc}")
