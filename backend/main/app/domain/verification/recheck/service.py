"""Re-check service — S44."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.recheck.models import (
    CreateRecheckRequestDto,
    RecheckRequestDto,
    RecheckStatus,
    ReviewRecheckDto,
    SubmitRecheckDto,
    UpdateRecheckRequestDto,
    SearchRecheckRequestDto,
)
from main.app.domain.verification.recheck.repo import RecheckRequestRepo
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
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
class RecheckService:
    def __init__(self, repo: RecheckRequestRepo, ver_repo: VerificationRepo):
        self._repo = repo
        self._ver_repo = ver_repo

    async def submit(
        self, verification_id: str, customer_id: str, dto: SubmitRecheckDto,
    ) -> RecheckRequestDto:
        ver = await self._ver_repo.get_model(verification_id)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        if VerificationStatus(ver.status) != VerificationStatus.COMPLETED:
            raise ValidationException(message="Re-check only available on COMPLETED verifications")

        row = await self._repo.create(CreateRecheckRequestDto(
            verification_id=verification_id,
            reason=dto.reason,
            scope_roles=json.dumps(dto.scope_roles),
            status=RecheckStatus.PENDING.value,
            requested_by=customer_id,
        ))
        return self._to_dto(row)

    async def list_pending(self) -> List[RecheckRequestDto]:
        rows = await self._repo.get_all(SearchRecheckRequestDto(status=RecheckStatus.PENDING.value))
        return [self._to_dto(r) for r in rows]

    async def approve(self, request_id: str, admin_id: str) -> RecheckRequestDto:
        row = await self._repo.get_model(request_id)
        if row is None:
            raise ResourceNotFoundException(resource="RecheckRequest")
        if row.status != RecheckStatus.PENDING.value:
            raise ValidationException(message="Only PENDING re-check requests can be approved")

        await self._repo.update(request_id, UpdateRecheckRequestDto(
            status=RecheckStatus.APPROVED.value,
            reviewed_by=admin_id,
            reviewed_at=str(Utils.datetime_now()),
        ))

        # Transition verification back to IN_PROGRESS
        from main.app.domain.verification.service import VerificationService
        ver_svc: VerificationService = di[VerificationService]
        await ver_svc.transition(str(row.verification_id), VerificationStatus.IN_PROGRESS, actor_id=admin_id)

        # Create new tasks for scope_roles
        try:
            scope_roles = json.loads(row.scope_roles or "[]")
            from main.app.domain.verification.task.service import TaskService
            task_svc: TaskService = di[TaskService]
            ver = await self._ver_repo.get_model(str(row.verification_id))
            for role in scope_roles:
                from main.app.domain.verification.task.models import CreateTaskDto, TaskStatus
                from main.appodus_utils import Utils as _u
                await task_svc._tasks.create_return_model(CreateTaskDto(
                    verification_id=str(row.verification_id),
                    role=role,
                    status=TaskStatus.PENDING,
                    pool_released_at=Utils.datetime_now(),
                ))
        except Exception as exc:
            logger.warning(f"Failed to create re-check tasks: {exc}")

        # Notify customer
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            ver = await self._ver_repo.get_model(str(row.verification_id))
            notif_svc: NotificationService = di[NotificationService]
            await notif_svc.emit(
                NotificationEvent.RECHECK_DECISION,
                recipient_id=str(ver.customer_id) if ver else "",
                context={"decision": "approved"},
                entity_type="RecheckRequest",
                entity_id=request_id,
            )
        except Exception as exc:
            logger.warning(f"Notification emit failed (recheck approve): {exc}")

        return self._to_dto(await self._repo.get_model(request_id))

    async def reject(self, request_id: str, admin_id: str, dto: ReviewRecheckDto) -> RecheckRequestDto:
        row = await self._repo.get_model(request_id)
        if row is None:
            raise ResourceNotFoundException(resource="RecheckRequest")
        await self._repo.update(request_id, UpdateRecheckRequestDto(
            status=RecheckStatus.REJECTED.value,
            reviewed_by=admin_id,
            reviewed_at=str(Utils.datetime_now()),
            rejection_reason=dto.rejection_reason,
        ))
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            ver = await self._ver_repo.get_model(str(row.verification_id))
            notif_svc: NotificationService = di[NotificationService]
            await notif_svc.emit(
                NotificationEvent.RECHECK_DECISION,
                recipient_id=str(ver.customer_id) if ver else "",
                context={"decision": "rejected"},
                entity_type="RecheckRequest",
                entity_id=request_id,
            )
        except Exception as exc:
            logger.warning(f"Notification emit failed (recheck reject): {exc}")

        return self._to_dto(await self._repo.get_model(request_id))

    def _to_dto(self, row) -> RecheckRequestDto:
        scope_roles = []
        try:
            scope_roles = json.loads(row.scope_roles or "[]")
        except Exception:
            pass
        return RecheckRequestDto(
            id=str(row.id),
            verification_id=str(row.verification_id),
            reason=row.reason,
            scope_roles=scope_roles,
            status=RecheckStatus(row.status),
            requested_by=str(row.requested_by),
            reviewed_by=str(row.reviewed_by) if row.reviewed_by else None,
            reviewed_at=str(row.reviewed_at) if row.reviewed_at else None,
            rejection_reason=row.rejection_reason,
            price=float(row.price) if row.price else None,
            date_created=str(row.date_created),
        )
