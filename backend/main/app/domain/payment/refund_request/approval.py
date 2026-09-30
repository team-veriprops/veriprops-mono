"""Finance deciding a refund request (§8.5, §18.1): the only path by which a customer's money
leaves.

Approve: the request is claimed (two Finance admins approving at once refund once), a closing
case is finished (delivered work paid, the rest cancelled), and the refund goes out — last,
because money leaves at the gateway as it runs and nothing may roll back after it. What the
gateways did is returned, so Finance is told when one refused (that charge waits in the
refunds-to-retry list, owing its share).

Reject: nothing is sent; a closing case goes back to work, and an upheld dispute reopens for ops
to decide again.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.models import RefundOutcome
from main.app.domain.payment.refund_request.models import (
    RefundRequestDto,
    RefundRequestStatus,
    RefundSource,
)
from main.app.domain.payment.refund_request.repo import RefundRequestRepo
from main.app.domain.payment.refund_request.service import RefundRequestService, refund_request_to_dto
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.closure.service import CaseClosureService
from main.app.domain.verification.dispute.service import DisputeService
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Object, Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ValidationException


class RefundDecisionDto(Object):
    request: RefundRequestDto
    # Approval only: what the gateways did. A refused charge waits in the refunds-to-retry list.
    outcome: Optional[RefundOutcome] = None


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class RefundApprovalService:
    def __init__(
        self,
        refund_request_repo: RefundRequestRepo,
        refund_request_service: RefundRequestService,
        case_closure_service: CaseClosureService,
        dispute_service: DisputeService,
        payment_service: PaymentService,
        verification_repo: VerificationRepo,
        audit_service: AuditLogService,
    ):
        self._repo = refund_request_repo
        self._requests = refund_request_service
        self._closures = case_closure_service
        self._disputes = dispute_service
        self._payments = payment_service
        self._verifications = verification_repo
        self._audit = audit_service

    async def approve(self, request_id: str, admin_id: str, note: Optional[str]) -> RefundDecisionDto:
        request = await self._decide(request_id, RefundRequestStatus.APPROVED, admin_id, note)
        vid = request.verification_id
        if request.source == RefundSource.CASE_CLOSURE.value:
            await self._closures.finalize(vid, admin_id, request.note)
        elif request.source == RefundSource.DISPUTE_UPHELD.value:
            await self._disputes.settle_full_refund(vid, admin_id)
        self._audit.schedule(
            action=AuditActionType.REFUND_APPROVED,
            resource_type="refund_request", resource_id=request.id, actor_id=admin_id,
            details={"verification_id": vid, "source": request.source, "amount_minor": request.amount_minor,
                     "note": note},
        )
        await publish_domain_event(DomainEvent(
            type=EventType.REFUND_INITIATED, verification_id=vid,
            recipient_user_ids=(str(request.customer_id),), data={"amount_minor": request.amount_minor},
        ))
        dto = refund_request_to_dto(request, await self._vid(vid))
        # Last: money leaves at the gateway here, so nothing after it may roll back.
        outcome = await self._payments.refund(
            vid, request.amount_minor, admin_id, reason=f"{request.source}:{request.reason or ''}",
            payment_ids=[request.payment_id] if request.payment_id else None,
        )
        return RefundDecisionDto(request=dto, outcome=outcome)

    async def reject(self, request_id: str, admin_id: str, note: Optional[str]) -> RefundDecisionDto:
        if not note or not note.strip():
            raise ValidationException(message="Say why the refund is rejected: the requester is told.")
        request = await self._decide(request_id, RefundRequestStatus.REJECTED, admin_id, note.strip())
        if request.source == RefundSource.CASE_CLOSURE.value:
            await self._closures.lift_hold(request.verification_id, admin_id, note.strip())
        elif request.source == RefundSource.DISPUTE_UPHELD.value:
            await self._disputes.reopen_refused_refund(request.verification_id, admin_id, note.strip())
        self._audit.schedule(
            action=AuditActionType.REFUND_REJECTED,
            resource_type="refund_request", resource_id=request.id, actor_id=admin_id,
            details={"verification_id": request.verification_id, "source": request.source,
                     "amount_minor": request.amount_minor, "note": note.strip()},
        )
        return RefundDecisionDto(request=refund_request_to_dto(request, await self._vid(request.verification_id)))

    async def _decide(self, request_id: str, to: RefundRequestStatus, admin_id: str, note: Optional[str]):
        request = await self._requests.get(request_id)
        decided = await self._repo.claim_transition(
            request.id, [RefundRequestStatus.PENDING], to,
            decided_by=admin_id, decided_at=Utils.datetime_now(), decision_note=note,
        )
        if decided is None:
            raise InvalidResourceStateException(
                resource="refund_request", message="This refund has already been decided.",
            )
        return decided

    async def _vid(self, verification_id: str) -> str:
        verification = await self._verifications.get_model(verification_id)
        return verification.vid if verification else ""
