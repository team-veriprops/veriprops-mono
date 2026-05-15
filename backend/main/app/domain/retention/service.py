"""RetentionPolicyService — NDPR data retention & erasure (S58)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from kink import inject, di

from main.app.domain.audit.models import AuditActionType
from main.app.domain.retention.models import (
    CreateErasureRequestDto,
    DataErasureRequest,
    ErasureRequestDto,
    ErasureRequestPageDto,
    ErasureStatus,
    UpdateErasureRequestDto,
)
from main.app.domain.retention.repo import DataErasureRequestRepo
from main.app.domain.user.repo import UserRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)

if TYPE_CHECKING:
    from loguru import Logger
logger: "Logger" = di["logger"]

# Non-terminal verification statuses — erasure blocked while any of these exist
_NON_TERMINAL = frozenset([
    "DRAFT", "SUBMITTED", "PAYMENT_PENDING", "PAID", "IN_PROGRESS", "UNDER_REVIEW", "DISPUTED",
])


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class RetentionPolicyService:
    def __init__(self, repo: DataErasureRequestRepo, user_repo: UserRepo):
        self._repo = repo
        self._user_repo = user_repo

    async def get_latest_for_user(self, user_id: str) -> Optional[ErasureRequestDto]:
        row = await self._repo.get_latest_for_user(user_id)
        return self._to_dto(row) if row else None

    async def request_erasure(self, user_id: str, reason: Optional[str]) -> ErasureRequestDto:
        # Block if an active request already exists
        existing = await self._repo.get_active_for_user(user_id)
        if existing:
            raise InvalidResourceStateException(
                resource="DataErasureRequest",
                message="An active erasure request already exists for this user",
            )

        # Block if user has any non-terminal verifications
        await self._assert_no_active_verifications(user_id)

        row = await self._repo.create_return_model(
            CreateErasureRequestDto(
                user_id=user_id,
                reason=reason,
                requested_at=datetime.now(timezone.utc),
            )
        )

        from main.app.domain.audit.service import AuditLogService
        audit_svc: AuditLogService = di[AuditLogService]
        audit_svc.schedule(
            AuditActionType.DATA_ERASURE_REQUESTED,
            resource_type="USER",
            resource_id=user_id,
            actor_id=user_id,
            meta={"reason": reason},
        )

        return self._to_dto(row)

    async def approve_erasure(self, request_id: str, admin_id: str) -> ErasureRequestDto:
        row = await self._repo.get_model(request_id)
        if row is None:
            raise ResourceNotFoundException(resource="DataErasureRequest")
        if row.status != ErasureStatus.PENDING.value:
            raise InvalidResourceStateException(
                resource="DataErasureRequest",
                message=f"Cannot approve a request in status {row.status}",
            )
        await self._repo.update(
            request_id,
            UpdateErasureRequestDto(
                status=ErasureStatus.APPROVED.value,
                reviewed_by=admin_id,
                reviewed_at=datetime.now(timezone.utc),
            ),
        )
        from main.app.domain.audit.service import AuditLogService
        audit_svc: AuditLogService = di[AuditLogService]
        audit_svc.schedule(
            AuditActionType.DATA_ERASURE_APPROVED,
            resource_type="DATA_ERASURE_REQUEST",
            resource_id=request_id,
            actor_id=admin_id,
            from_state=ErasureStatus.PENDING.value,
            to_state=ErasureStatus.APPROVED.value,
        )
        row = await self._repo.get_model(request_id)
        return self._to_dto(row)

    async def reject_erasure(
            self, request_id: str, admin_id: str, reason: str
    ) -> ErasureRequestDto:
        row = await self._repo.get_model(request_id)
        if row is None:
            raise ResourceNotFoundException(resource="DataErasureRequest")
        if row.status != ErasureStatus.PENDING.value:
            raise InvalidResourceStateException(
                resource="DataErasureRequest",
                message=f"Cannot reject a request in status {row.status}",
            )
        await self._repo.update(
            request_id,
            UpdateErasureRequestDto(
                status=ErasureStatus.REJECTED.value,
                reviewed_by=admin_id,
                reviewed_at=datetime.now(timezone.utc),
                rejection_reason=reason,
            ),
        )
        from main.app.domain.audit.service import AuditLogService
        audit_svc: AuditLogService = di[AuditLogService]
        audit_svc.schedule(
            AuditActionType.DATA_ERASURE_REJECTED,
            resource_type="DATA_ERASURE_REQUEST",
            resource_id=request_id,
            actor_id=admin_id,
            from_state=ErasureStatus.PENDING.value,
            to_state=ErasureStatus.REJECTED.value,
            meta={"reason": reason},
        )
        row = await self._repo.get_model(request_id)
        return self._to_dto(row)

    async def execute_erasure(self, request_id: str, admin_id: str) -> None:
        row = await self._repo.get_model(request_id)
        if row is None:
            raise ResourceNotFoundException(resource="DataErasureRequest")
        if row.status != ErasureStatus.APPROVED.value:
            raise InvalidResourceStateException(
                resource="DataErasureRequest",
                message=f"Cannot execute a request in status {row.status}",
            )

        user_id = row.user_id
        short_user_id = user_id.replace("-", "")[:8]

        await self._user_repo.erase_user(user_id=user_id, short_user_id=short_user_id)

        await self._repo.update(
            request_id,
            UpdateErasureRequestDto(
                status=ErasureStatus.EXECUTED.value,
                executed_at=datetime.now(timezone.utc),
            ),
        )

        from main.app.domain.audit.service import AuditLogService
        audit_svc: AuditLogService = di[AuditLogService]
        audit_svc.schedule(
            AuditActionType.DATA_ERASURE_EXECUTED,
            resource_type="USER",
            resource_id=user_id,
            actor_id=admin_id,
            from_state=ErasureStatus.APPROVED.value,
            to_state=ErasureStatus.EXECUTED.value,
        )

    async def list_requests(
            self,
            status: Optional[str] = None,
            page: int = 0,
            page_size: int = 20,
    ) -> ErasureRequestPageDto:
        rows, total = await self._repo.list_by_status(status, offset=page * page_size, limit=page_size)
        return ErasureRequestPageDto(
            items=[self._to_dto(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _assert_no_active_verifications(self, user_id: str) -> None:
        has_active_verification = await self._user_repo.has_active_verification(user_id=user_id,
                                                                                non_terminal_verification_status=_NON_TERMINAL)
        if has_active_verification:
            raise InvalidResourceStateException(
                resource="DataErasureRequest",
                message="Cannot request erasure while active verifications exist",
            )

    @staticmethod
    def _to_dto(row: DataErasureRequest) -> ErasureRequestDto:
        return ErasureRequestDto(
            id=str(row.id),
            user_id=row.user_id,
            reason=row.reason,
            status=ErasureStatus(row.status),
            requested_at=row.requested_at,
            reviewed_by=row.reviewed_by,
            reviewed_at=row.reviewed_at,
            executed_at=row.executed_at,
            rejection_reason=row.rejection_reason,
        )
