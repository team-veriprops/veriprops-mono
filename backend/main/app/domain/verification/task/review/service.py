"""Task review service — admin approve/reject/reopen (S28)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.task.models import TaskStatus, UpdateTaskDto
from main.app.domain.verification.task.repo import TaskRepo
from main.app.domain.verification.task.review.models import (
    TaskReviewDecision,
    TaskReviewDto,
)
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

_MIN_REASON_LENGTH = 30


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TaskReviewService:
    def __init__(
        self,
        task_repo: TaskRepo,
        audit: AuditLogService,
    ):
        self._tasks = task_repo
        self._audit = audit

    async def approve(
        self, task_id: str, admin_id: str, note: Optional[str] = None,
    ) -> TaskReviewDto:
        task = await self._get_submitted_or_raise(task_id)
        now = datetime.now(timezone.utc)
        await self._tasks.update(task_id, UpdateTaskDto(status=TaskStatus.APPROVED))
        self._audit.schedule(
            AuditActionType.TASK_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=admin_id,
            from_state=TaskStatus.SUBMITTED.value,
            to_state=TaskStatus.APPROVED.value,
            details={"action": "ADMIN_APPROVE", "note": note},
        )
        await self._derive_verification_status(task.verification_id)
        await self._recompute_trust_score(task.verification_id)
        await self._publish(task.verification_id, "task_approved", task_id)
        await self._emit_notification_safe(task, "approved")
        await self._compute_commission_safe(task, admin_id)
        if task.agent_id:
            await self._restore_availability_safe(task.agent_id)
        return TaskReviewDto(
            task_id=task_id,
            decision=TaskReviewDecision.APPROVED,
            reason=note,
            reviewed_by=admin_id,
            reviewed_at=now,
        )

    async def reject(
        self, task_id: str, admin_id: str, reason: str,
    ) -> TaskReviewDto:
        if len(reason.strip()) < _MIN_REASON_LENGTH:
            raise ValidationException(
                message=f"Rejection reason must be at least {_MIN_REASON_LENGTH} characters"
            )
        task = await self._get_submitted_or_raise(task_id)
        now = datetime.now(timezone.utc)
        # SUBMITTED → REJECTED → IN_PROGRESS so agent can rework
        await self._tasks.update(task_id, UpdateTaskDto(status=TaskStatus.REJECTED))
        await self._tasks.update(task_id, UpdateTaskDto(status=TaskStatus.IN_PROGRESS))
        self._audit.schedule(
            AuditActionType.TASK_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=admin_id,
            from_state=TaskStatus.SUBMITTED.value,
            to_state=TaskStatus.IN_PROGRESS.value,
            details={"action": "ADMIN_REJECT", "reason": reason},
        )
        await self._derive_verification_status(task.verification_id)
        await self._publish(task.verification_id, "task_rejected", task_id)
        await self._emit_notification_safe(task, "rejected")
        return TaskReviewDto(
            task_id=task_id,
            decision=TaskReviewDecision.REJECTED,
            reason=reason,
            reviewed_by=admin_id,
            reviewed_at=now,
        )

    async def reopen(
        self, task_id: str, admin_id: str, reason: str,
    ) -> TaskReviewDto:
        if len(reason.strip()) < _MIN_REASON_LENGTH:
            raise ValidationException(
                message=f"Reopen reason must be at least {_MIN_REASON_LENGTH} characters"
            )
        task = await self._tasks.get_task(task_id)
        if task is None:
            raise ResourceNotFoundException(resource="Task")
        if task.status != TaskStatus.APPROVED.value:
            raise ValidationException(
                message=f"Only APPROVED tasks can be reopened (current status: {task.status})"
            )
        now = datetime.now(timezone.utc)
        await self._tasks.update(task_id, UpdateTaskDto(status=TaskStatus.IN_PROGRESS))
        self._audit.schedule(
            AuditActionType.TASK_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=admin_id,
            from_state=TaskStatus.APPROVED.value,
            to_state=TaskStatus.IN_PROGRESS.value,
            details={"action": "ADMIN_REOPEN", "reason": reason},
        )
        await self._derive_verification_status(task.verification_id)
        await self._publish(task.verification_id, "task_reopened", task_id)
        return TaskReviewDto(
            task_id=task_id,
            decision=TaskReviewDecision.APPROVED,
            reason=reason,
            reviewed_by=admin_id,
            reviewed_at=now,
        )

    # ── helpers ───────────────────────────────────────────────────────

    async def _get_submitted_or_raise(self, task_id: str):
        task = await self._tasks.get_task(task_id)
        if task is None:
            raise ResourceNotFoundException(resource="Task")
        if task.status != TaskStatus.SUBMITTED.value:
            raise ValidationException(
                message=f"Task must be in SUBMITTED state to review (current: {task.status})"
            )
        return task

    async def _derive_verification_status(self, verification_id: str) -> None:
        from main.app.domain.verification.task.service import TaskService
        svc: TaskService = di[TaskService]
        await svc._derive_and_update_verification_status(verification_id)

    async def _recompute_trust_score(self, verification_id: str) -> None:
        try:
            from main.app.domain.verification.repo import VerificationRepo
            from main.app.domain.verification.scoring.service import TrustScoreService
            ver_repo: VerificationRepo = di[VerificationRepo]
            ver = await ver_repo.get(verification_id)
            if ver is None:
                return
            svc: TrustScoreService = di[TrustScoreService]
            await svc.recompute_for_verification(verification_id, tier=ver.tier)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Trust score recompute failed for {verification_id}: {exc}")

    async def _publish(self, verification_id: str, event: str, task_id: str) -> None:
        try:
            from main.appodus_utils.db.redis_utils import RedisUtils
            redis: RedisUtils = di[RedisUtils]
            await redis.publish(
                f"verifications:{verification_id}",
                {"event": event, "task_id": task_id, "verification_id": verification_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE publish failed ({event}): {exc}")

    async def _emit_notification_safe(self, task, action: str) -> None:
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            notif_svc: NotificationService = di[NotificationService]
            if action == "rejected":
                await notif_svc.emit(
                    NotificationEvent.REVISION_REQUEST,
                    recipient_id=str(task.agent_id or ""),
                    context={},
                    entity_type="Task",
                    entity_id=str(task.id),
                )
        except Exception as exc:
            logger.warning(f"Notification emit failed (task review {action}): {exc}")

    async def _restore_availability_safe(self, agent_id: str) -> None:
        try:
            from main.app.domain.verification.task.service import TaskService
            svc: TaskService = di[TaskService]
            await svc._maybe_restore_availability(agent_id)
        except Exception as exc:
            logger.warning(f"Availability restore failed for agent {agent_id}: {exc}")

    async def _compute_commission_safe(self, task, admin_id: str) -> None:
        try:
            from main.app.domain.commission.service import CommissionService
            from main.app.domain.verification.repo import VerificationRepo
            from main.app.domain.payment.repo import PaymentRepo
            from main.app.domain.payment.models import PaymentStatus, SearchPaymentDto
            commission_svc: CommissionService = di[CommissionService]
            ver_repo: VerificationRepo = di[VerificationRepo]
            payment_repo: PaymentRepo = di[PaymentRepo]
            ver = await ver_repo.get(str(task.verification_id))
            if ver is None or not task.agent_id:
                return
            payments = await payment_repo.get_all(SearchPaymentDto(verification_id=str(task.verification_id)))
            succeeded = [p for p in payments if p.status == PaymentStatus.SUCCEEDED.value]
            gross_amount = float(succeeded[0].amount_minor) / 100 if succeeded else 0.0
            await commission_svc.compute_and_record(
                task_id=str(task.id),
                agent_id=str(task.agent_id),
                verification_id=str(task.verification_id),
                role=str(task.role),
                tier=str(ver.tier),
                gross_amount=gross_amount,
            )
        except Exception as exc:
            logger.warning(f"Commission compute failed for task {task.id}: {exc}")
