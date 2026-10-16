"""Filing and reading refund requests (§8.5, §18.1). Deciding them is refund_approval.py's.

Every caller that needs a customer's money returned — closing a paid case, an upheld dispute,
a charge that landed on a case already closed — files here instead of refunding. Nothing is
sent until Finance approves.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.refund_request.models import (
    CreateRefundRequestDto,
    RefundRequest,
    RefundRequestDto,
    RefundRequestStatus,
    RefundSource,
)
from main.app.domain.payment.refund_request.repo import REFUND_REQUEST_SORTABLE, RefundRequestRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.models import Page
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ResourceNotFoundException


def refund_request_to_dto(r: RefundRequest, vid: str) -> RefundRequestDto:
    return RefundRequestDto(
        id=Utils.uuid_to_hex(r.id), verification_id=r.verification_id, vid=vid, customer_id=r.customer_id,
        source=RefundSource(r.source), status=RefundRequestStatus(r.status), amount_minor=r.amount_minor,
        currency=TransactionCurrency(r.currency), reason=r.reason, note=r.note, evidence_ref=r.evidence_ref,
        requested_by=r.requested_by, decided_by=r.decided_by, decided_at=r.decided_at,
        decision_note=r.decision_note, date_created=r.date_created,
    )


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class RefundRequestService:
    def __init__(self, refund_request_repo: RefundRequestRepo, audit_service: AuditLogService):
        self._requests = refund_request_repo
        self._audit = audit_service

    async def file(
        self, *, verification_id: str, customer_id: str, source: RefundSource, amount_minor: int,
        currency: TransactionCurrency, requested_by: Optional[str], reason: Optional[str] = None,
        note: Optional[str] = None, evidence_ref: Optional[str] = None, payment_id: Optional[str] = None,
    ) -> RefundRequest:
        """File a request for Finance. One may be pending per case — except late charges,
        each of which is its own charge (`payment_id`) and waits on its own; a closing case or
        an upheld dispute is refused while one waits."""
        verification_id = Utils.uuid_to_hex(verification_id)
        if source != RefundSource.LATE_CHARGE and await self._requests.get_pending_for_verification(verification_id):
            raise InvalidResourceStateException(
                resource="refund_request",
                message="A refund for this case is already waiting for Finance.",
            )
        request = await self._requests.create_return_model(CreateRefundRequestDto(
            verification_id=verification_id, customer_id=customer_id, source=source,
            amount_minor=amount_minor, currency=currency, reason=reason, note=note,
            evidence_ref=evidence_ref, requested_by=requested_by,
            payment_id=Utils.uuid_to_hex(payment_id) if payment_id else None,
        ))
        self._audit_filed(request, requested_by, added_minor=amount_minor)
        return request

    async def get(self, request_id: str) -> RefundRequest:
        request = await self._requests.get_model(request_id)
        if request is None:
            raise ResourceNotFoundException(resource="refund_request")
        return request

    async def get_pending_for_verification(self, verification_id: str) -> Optional[RefundRequest]:
        return await self._requests.get_pending_for_verification(Utils.uuid_to_hex(verification_id))

    async def page(
        self, page: int, page_size: int, status: Optional[RefundRequestStatus], order_by: Optional[str] = None,
    ) -> Page[RefundRequestDto]:
        """Finance's queue (PENDING, oldest first) or the record (newest first), unless *order_by* says otherwise."""
        rows, total, applied = await self._requests.page_with_vid(page, page_size, status, order_by)
        return DbUtils.build_page(
            [refund_request_to_dto(r, vid) for r, vid in rows], total, page, page_size,
            sort=applied, sortable=REFUND_REQUEST_SORTABLE,
        )

    def _audit_filed(self, request: RefundRequest, actor_id: Optional[str], added_minor: int) -> None:
        self._audit.schedule(
            action=AuditActionType.REFUND_REQUESTED,
            resource_type="refund_request", resource_id=request.id, actor_id=actor_id,
            details={"verification_id": request.verification_id, "source": request.source,
                     "amount_minor": added_minor, "reason": request.reason},
        )
