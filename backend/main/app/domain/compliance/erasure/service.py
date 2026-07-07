"""Data-erasure request service (PRD §18.1, §19.1 / §4.11).

Orchestrates the NDPA erasure lifecycle: a data subject (or an admin) opens a
request; an admin with MANAGE_COMPLIANCE approves or rejects it; approval is
carried out by the irreversible pseudonymisation step (``PiiPseudonymiser``). Every
transition is audit-logged, and the subject is notified in-app of the outcome.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.machine import erasure_request_state_machine
from main.app.core.state.status import ErasureRequestState
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.compliance.erasure.models import (
    CreateDataErasureRequestDto,
    DataErasureRequest,
    DataErasureRequestDto,
    erasure_to_dto,
)
from main.app.domain.compliance.erasure.pseudonymiser import PiiPseudonymiser
from main.app.domain.compliance.erasure.repo import DataErasureRequestRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)

_RESOURCE = "data_erasure_request"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ErasureService:
    def __init__(
        self,
        erasure_repo: DataErasureRequestRepo,
        user_repo: UserRepo,
        config_service: ConfigService,
        pseudonymiser: PiiPseudonymiser,
        audit_service: AuditLogService,
    ):
        self._repo = erasure_repo
        self._users = user_repo
        self._config = config_service
        self._pseudonymiser = pseudonymiser
        self._audit = audit_service

    # ── Self-service (data subject) ───────────────────────────────

    async def request(
        self, subject_user_id: str, requested_by_user_id: str, reason: Optional[str]
    ) -> DataErasureRequest:
        subject = await self._users.get_model(subject_user_id)
        if not subject:
            raise ResourceNotFoundException(resource="user")
        if await self._repo.get_open_for_user(subject_user_id):
            raise InvalidResourceStateException(
                resource=_RESOURCE,
                message="An erasure request is already in progress for this account.",
            )
        sla_days = await self._config.get_int(ConfigKey.ERASURE_REQUEST_REVIEW_SLA_DAYS)
        row = await self._repo.create_return_model(CreateDataErasureRequestDto(
            subject_user_id=subject_user_id,
            requested_by_user_id=requested_by_user_id,
            reason=reason,
            status=ErasureRequestState.PENDING,
            sla_due_at=Utils.datetime_now() + timedelta(days=sla_days),
        ))
        self._audit.schedule(
            action=AuditActionType.DATA_ERASURE_REQUESTED,
            resource_type=_RESOURCE, resource_id=row.id, actor_id=requested_by_user_id,
            to_state=ErasureRequestState.PENDING.value,
            details={"subject_user_id": subject_user_id},
        )
        await self._notify(subject_user_id, ErasureRequestState.PENDING,
                           "We've received your data-erasure request and will review it shortly.")
        return row

    async def list_for_user(self, subject_user_id: str) -> List[DataErasureRequest]:
        return await self._repo.list_for_user(subject_user_id)

    # ── Admin review ──────────────────────────────────────────────

    async def get(self, request_id: str) -> DataErasureRequest:
        row = await self._repo.get_model(request_id)
        if not row:
            raise ResourceNotFoundException(resource=_RESOURCE)
        return row

    async def page(self, status: Optional[str], page: int, page_size: int) -> Page[DataErasureRequestDto]:
        rows, total = await self._repo.page_by_status(status, offset=page * page_size, limit=page_size)
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[DataErasureRequestDto](
            items=[erasure_to_dto(r) for r in rows],
            meta=PaginationMeta(
                page=page, page_size=page_size, count=len(rows), total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    async def approve(self, request_id: str, admin_id: str) -> DataErasureRequest:
        row = await self.get(request_id)
        self._transition(row, ErasureRequestState.APPROVED)
        row.reviewed_by_user_id = admin_id
        row.reviewed_at = Utils.datetime_now()
        self._audit.schedule(
            action=AuditActionType.DATA_ERASURE_APPROVED,
            resource_type=_RESOURCE, resource_id=row.id, actor_id=admin_id,
            from_state=ErasureRequestState.PENDING.value, to_state=ErasureRequestState.APPROVED.value,
            details={"subject_user_id": row.subject_user_id},
        )
        await self._notify(row.subject_user_id, ErasureRequestState.APPROVED,
                           "Your data-erasure request has been approved and will be carried out.")
        return row

    async def reject(self, request_id: str, admin_id: str, note: Optional[str]) -> DataErasureRequest:
        row = await self.get(request_id)
        self._transition(row, ErasureRequestState.REJECTED)
        row.reviewed_by_user_id = admin_id
        row.reviewed_at = Utils.datetime_now()
        row.decision_note = note
        self._audit.schedule(
            action=AuditActionType.DATA_ERASURE_REJECTED,
            resource_type=_RESOURCE, resource_id=row.id, actor_id=admin_id,
            from_state=ErasureRequestState.PENDING.value, to_state=ErasureRequestState.REJECTED.value,
            details={"subject_user_id": row.subject_user_id, "note": note},
        )
        await self._notify(row.subject_user_id, ErasureRequestState.REJECTED,
                           "Your data-erasure request could not be approved. See the details for more.")
        return row

    async def execute(self, request_id: str, admin_id: str) -> DataErasureRequest:
        """Irreversibly pseudonymise the subject's PII (§4.11). Idempotent."""
        row = await self.get(request_id)
        if row.status == ErasureRequestState.EXECUTED.value:
            return row  # already carried out — no-op
        self._transition(row, ErasureRequestState.EXECUTED)

        token = self._pseudonymiser.token_for(row.subject_user_id)
        surfaces = await self._pseudonymiser.pseudonymise(row.subject_user_id, token)

        row.executed_at = Utils.datetime_now()
        row.pseudonym_token = token
        self._audit.schedule(
            action=AuditActionType.DATA_ERASURE_EXECUTED,
            resource_type=_RESOURCE, resource_id=row.id, actor_id=admin_id,
            from_state=ErasureRequestState.APPROVED.value, to_state=ErasureRequestState.EXECUTED.value,
            details={"subject_user_id": row.subject_user_id, "surfaces": surfaces},
        )
        return row

    # ── helpers ───────────────────────────────────────────────────

    def _transition(self, row: DataErasureRequest, target: ErasureRequestState) -> None:
        erasure_request_state_machine.assert_can_transition(
            row.status, target.value, resource=_RESOURCE
        )
        row.status = target.value

    async def _notify(self, subject_user_id: str, state: ErasureRequestState, message: str) -> None:
        await publish_domain_event(DomainEvent(
            type=EventType.ERASURE_STATUS_CHANGED,
            recipient_user_ids=(subject_user_id,),
            data={"status": state.value, "message": message},
        ))
