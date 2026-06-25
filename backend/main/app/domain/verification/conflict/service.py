"""Conflict detection service — PRD Phase 8 (S29)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, TYPE_CHECKING

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.conflict.models import (
    ConflictFlagDto,
    ConflictStatus,
    CreateConflictFlagDto,
    ResolveConflictDto,
    UpdateConflictFlagDto,
)
from main.app.domain.verification.conflict.repo import ConflictFlagRepo
from main.app.domain.verification.conflict.rules import run_all_rules
from main.app.domain.verification.task.repo import TaskRepo
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
class ConflictService:
    def __init__(
        self,
        conflict_repo: ConflictFlagRepo,
        task_repo: TaskRepo,
        audit: AuditLogService,
    ):
        self._conflicts = conflict_repo
        self._tasks = task_repo
        self._audit = audit

    async def detect_and_store(self, verification_id: str) -> List[ConflictFlagDto]:
        """Run all conflict rules against submitted tasks and persist any flags."""
        tasks = await self._tasks.list_for_verification(verification_id)
        flags = run_all_rules(tasks, verification_id)
        stored: List[ConflictFlagDto] = []
        for flag in flags:
            record = await self._conflicts.create_return_model(
                CreateConflictFlagDto(
                    verification_id=verification_id,
                    rule_id=flag.rule_id,
                    severity=flag.severity,
                    description=flag.description,
                )
            )
            stored.append(self._to_dto(record))
            self._audit.schedule(
                AuditActionType.VERIFICATION_STATE_CHANGED,
                resource_type="ConflictFlag",
                resource_id=str(record.id),
                actor_id=None,
                details={
                    "action": "CONFLICT_DETECTED",
                    "rule_id": flag.rule_id,
                    "severity": flag.severity.value,
                    "verification_id": verification_id,
                },
            )
        if stored:
            await self._publish_conflict(verification_id)
        return stored

    async def list_for_verification(self, verification_id: str) -> List[ConflictFlagDto]:
        flags = await self._conflicts.list_for_verification(verification_id)
        return [self._to_dto(f) for f in flags]

    async def has_open_conflicts(self, verification_id: str) -> bool:
        return await self._conflicts.has_open(verification_id)

    async def resolve(
        self,
        conflict_id: str,
        admin_id: str,
        dto: ResolveConflictDto,
    ) -> ConflictFlagDto:
        flag = await self._conflicts.get_by_id(conflict_id)
        if flag is None:
            raise ResourceNotFoundException(resource="ConflictFlag")
        if flag.status != ConflictStatus.OPEN.value:
            raise ValidationException(message="Conflict is already resolved")

        if dto.action == "OVERRIDE":
            if not dto.note.strip():
                raise ValidationException(message="Override note is required")
            new_status = ConflictStatus.OVERRIDDEN
        elif dto.action == "REJECT_TASK":
            if not dto.task_id_to_reject:
                raise ValidationException(message="task_id_to_reject is required for REJECT_TASK action")
            from main.app.domain.verification.task.review.service import TaskReviewService
            review_svc: TaskReviewService = di[TaskReviewService]
            await review_svc.reject(
                dto.task_id_to_reject,
                admin_id,
                reason=f"Conflict resolution: {dto.note}",
            )
            new_status = ConflictStatus.TASK_REJECTED
        else:
            raise ValidationException(message=f"Unknown action: {dto.action}")

        now = datetime.now(timezone.utc)
        await self._conflicts.update(
            conflict_id,
            UpdateConflictFlagDto(
                status=new_status,
                resolution_note=dto.note,
                resolved_by=admin_id,
                resolved_at=now,
            ),
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="ConflictFlag",
            resource_id=conflict_id,
            actor_id=admin_id,
            details={"action": "CONFLICT_RESOLVED", "resolution": dto.action, "note": dto.note},
        )
        updated = await self._conflicts.get_by_id(conflict_id)
        return self._to_dto(updated)

    # ── helpers ───────────────────────────────────────────────────────

    async def _publish_conflict(self, verification_id: str) -> None:
        try:
            from main.appodus_utils.db.redis_utils import RedisUtils
            redis: RedisUtils = di[RedisUtils]
            await redis.publish(
                f"admin:{verification_id}",
                {"event": "conflict_detected", "verification_id": verification_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE publish failed (conflict_detected): {exc}")

    @staticmethod
    def _to_dto(flag) -> ConflictFlagDto:
        return ConflictFlagDto(
            id=str(flag.id),
            verification_id=flag.verification_id,
            rule_id=flag.rule_id,
            severity=flag.severity,
            description=flag.description,
            status=flag.status,
            resolution_note=flag.resolution_note,
            resolved_by=flag.resolved_by,
            resolved_at=flag.resolved_at,
            date_created=flag.date_created,
            date_updated=flag.date_updated,
        )
