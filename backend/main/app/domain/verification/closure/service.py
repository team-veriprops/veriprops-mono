"""Closing a paid case (PRD §3 refund & liability model, §6.4, §8.5) — see models.py for the flow.

Race-safe throughout: the hold is claimed on the case (only one close at a time, and only on a
case still open), the close is claimed on the reason it was held for, and each task is claimed
from the state it was read in. The refund itself is never sent from here: a close that owes
money files a request, and Finance's approval (refund_approval.py) finishes the close.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.realtime import VerificationEventType
from main.app.core.state.status import TaskState, VerificationStatus
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.refund_request.models import RefundSource
from main.app.domain.payment.refund_request.service import RefundRequestService
from main.app.domain.payment.service import PaymentService
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.verification.closure.models import (
    ClosureAgentImpactDto,
    ClosureQuoteDto,
    ClosureResultDto,
    CloseCaseDto,
    CloseReason,
)
from main.app.domain.verification.closure.policy import (
    CLOSABLE_STATUSES,
    closure_refund,
    closure_status,
    is_on_hold,
)
from main.app.domain.verification.models import Verification
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.review.service import ReviewService
from main.app.domain.verification.task.models import VerificationTask
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ResourceNotFoundException

# Delivered work, paid when the case closes.
_DELIVERED = {TaskState.SUBMITTED.value, TaskState.APPROVED.value}
# Undelivered work, cancelled when the case closes.
_UNDELIVERED = (TaskState.PENDING, TaskState.ASSIGNED, TaskState.ACCEPTED, TaskState.IN_PROGRESS, TaskState.REJECTED)
# Work an agent may be doing right now: who is told to stop, and to resume.
_IN_HAND = {TaskState.ASSIGNED.value, TaskState.ACCEPTED.value, TaskState.IN_PROGRESS.value, TaskState.REJECTED.value}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CaseClosureService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: VerificationTaskRepo,
        review_service: ReviewService,
        payment_service: PaymentService,
        refund_request_service: RefundRequestService,
        config_service: ConfigService,
        audit_service: AuditLogService,
    ):
        self._verifications = verification_repo
        self._tasks = task_repo
        self._reviews = review_service
        self._payments = payment_service
        self._refund_requests = refund_request_service
        self._config = config_service
        self._audit = audit_service

    async def quote(self, verification_id: str, reason: CloseReason, amount_minor: int | None = None) -> ClosureQuoteDto:
        """What closing for *reason* would do — the exact refund, how the case ends, and each
        agent's outcome — for the admin to confirm before anything happens."""
        verification = await self._open_case(verification_id)
        vid = Utils.uuid_to_hex(verification.id)
        refundable = await self._payments.refundable_minor(vid)
        refund = closure_refund(
            reason, VerificationStatus(verification.status), refundable,
            surcharge_pct=await self._config.get_int(ConfigKey.CANCELLATION_SURCHARGE_PCT),
            requested_minor=amount_minor,
        )
        tasks = await self._tasks.list_for_verification(vid)
        return ClosureQuoteDto(
            reason=reason, currency=TransactionCurrency(verification.currency),
            refundable_minor=refundable, refund_minor=refund,
            resulting_status=closure_status(reason), requires_approval=refund > 0,
            agents=[
                ClosureAgentImpactDto(
                    task_id=Utils.uuid_to_hex(t.id), role=t.role, agent_id=t.assigned_agent_id,
                    state=TaskState(t.state), paid=t.state in _DELIVERED and bool(t.assigned_agent_id),
                )
                for t in tasks if t.state != TaskState.CANCELLED.value
            ],
        )

    async def close(self, verification_id: str, dto: CloseCaseDto, admin_id: str) -> ClosureResultDto:
        """Close a paid case. Nothing to refund: it ends now. Money to return: it goes on hold,
        its agents are told to stop, and a refund request waits for Finance."""
        quote = await self.quote(verification_id, dto.reason, dto.amount_minor)
        verification = await self._open_case(verification_id)
        vid = Utils.uuid_to_hex(verification.id)
        held = await self._verifications.claim_transition(
            verification.id, CLOSABLE_STATUSES, expect={"closure_reason": None},
            closure_reason=dto.reason.value,
        )
        if held is None:
            raise InvalidResourceStateException(resource="verification", message="This verification has already moved on.")

        if quote.refund_minor == 0:
            status = await self.finalize(vid, admin_id, dto.note)
            return ClosureResultDto(status=status, on_hold=False, refund_minor=0, currency=quote.currency)

        request = await self._refund_requests.file(
            verification_id=vid, customer_id=verification.customer_id, source=RefundSource.CASE_CLOSURE,
            amount_minor=quote.refund_minor, currency=TransactionCurrency(verification.currency),
            requested_by=admin_id, reason=dto.reason.value, note=dto.note, evidence_ref=dto.evidence_ref,
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_ON_HOLD,
            resource_type="verification", resource_id=vid, actor_id=admin_id,
            details={"reason": dto.reason.value, "note": dto.note, "refund_minor": quote.refund_minor,
                     "refund_request_id": Utils.uuid_to_hex(request.id)},
        )
        tasks = await self._tasks.list_for_verification(vid)
        await self._tell_agents(vid, tasks, EventType.TASK_ON_HOLD, only_in_hand=True)
        await self._tell_customer(verification, EventType.CASE_ON_HOLD)
        return ClosureResultDto(
            status=VerificationStatus(verification.status), on_hold=True, refund_minor=quote.refund_minor,
            currency=quote.currency,
            refund_request_id=Utils.uuid_to_hex(request.id),
        )

    async def finalize(self, verification_id: str, actor_id: str, note: str | None) -> VerificationStatus:
        """End a case held for closing: delivered work is paid, the rest is cancelled, and
        everyone is told. Called by the close itself (nothing to refund) or by Finance's
        approval, which sends the refund after this."""
        verification = await self._get(verification_id)
        if not verification.closure_reason:
            raise InvalidResourceStateException(resource="verification", message="This verification is not being closed.")
        reason = CloseReason(verification.closure_reason)
        target = closure_status(reason)
        vid = Utils.uuid_to_hex(verification.id)
        from_status = verification.status  # read before the claim moves the row
        closed = await self._verifications.claim_transition(
            verification.id, CLOSABLE_STATUSES, target, expect={"closure_reason": reason.value},
        )
        if closed is None:
            raise InvalidResourceStateException(resource="verification", message="This verification has already moved on.")

        tasks = await self._tasks.list_for_verification(vid)
        await self._reviews.accrue_commissions(
            verification, [t for t in tasks if t.state in _DELIVERED and t.assigned_agent_id],
        )
        for task in tasks:
            if task.state not in {s.value for s in _UNDELIVERED}:
                continue
            from_state = task.state  # the claim refreshes the row
            if await self._tasks.claim_transition(
                task.id, [task.state], TaskState.CANCELLED, status_column="state", in_pool=False,
            ) is None:
                continue
            self._audit.schedule(
                action=AuditActionType.TASK_STATE_CHANGED,
                resource_type="verification_task", resource_id=task.id, actor_id=actor_id,
                from_state=from_state, to_state=TaskState.CANCELLED.value,
                details={"event": "case_closed", "role": task.role, "reason": reason.value},
            )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_FAILED if target == VerificationStatus.FAILED
            else AuditActionType.VERIFICATION_CANCELLED,
            resource_type="verification", resource_id=vid, actor_id=actor_id,
            from_state=from_status, to_state=target.value,
            details={"reason": reason.value, "note": note},
        )
        await self._tell_agents(vid, tasks, EventType.TASK_CASE_CLOSED, only_in_hand=False)
        await self._tell_customer(verification, EventType.CASE_CLOSED)
        return target

    async def lift_hold(self, verification_id: str, actor_id: str, note: str | None) -> None:
        """Finance declined the closing refund: the case goes back to work, and everyone
        who was told to stop is told to resume."""
        verification = await self._get(verification_id)
        if not is_on_hold(verification):
            raise InvalidResourceStateException(resource="verification", message="This verification is not on hold.")
        vid = Utils.uuid_to_hex(verification.id)
        held_for = verification.closure_reason  # the claim clears it on the row
        if await self._verifications.claim_transition(
            verification.id, CLOSABLE_STATUSES, expect={"closure_reason": held_for},
            closure_reason=None,
        ) is None:
            raise InvalidResourceStateException(resource="verification", message="This verification has already moved on.")
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_HOLD_LIFTED,
            resource_type="verification", resource_id=vid, actor_id=actor_id,
            details={"reason": held_for, "note": note},
        )
        tasks = await self._tasks.list_for_verification(vid)
        await self._tell_agents(vid, tasks, EventType.TASK_RESUMED, only_in_hand=True)
        await self._tell_customer(verification, EventType.CASE_RESUMED)

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, verification_id: str) -> Verification:
        verification = await self._verifications.get_model(verification_id)
        if verification is None:
            raise ResourceNotFoundException(resource="verification")
        return verification

    async def _open_case(self, verification_id: str) -> Verification:
        verification = await self._get(verification_id)
        if verification.status not in {s.value for s in CLOSABLE_STATUSES}:
            raise InvalidResourceStateException(
                resource="verification",
                message="Only a paid verification that has not finished can be closed; cancel an unpaid one instead.",
            )
        if verification.closure_reason:
            raise InvalidResourceStateException(
                resource="verification", message="This verification is already being closed; its refund is with Finance.",
            )
        return verification

    async def _tell_agents(self, vid: str, tasks: List[VerificationTask], event: EventType, *, only_in_hand: bool) -> None:
        agents = {
            t.assigned_agent_id for t in tasks
            if t.assigned_agent_id and (not only_in_hand or t.state in _IN_HAND)
        }
        if agents:
            await publish_domain_event(DomainEvent(
                type=event, verification_id=vid, recipient_user_ids=tuple(sorted(agents)),
                sse_event=VerificationEventType.TASK_UPDATED.value,
            ))

    async def _tell_customer(self, verification: Verification, event: EventType) -> None:
        await publish_domain_event(DomainEvent(
            type=event, verification_id=Utils.uuid_to_hex(verification.id),
            recipient_user_ids=(str(verification.customer_id),),
            sse_event=VerificationEventType.STATUS_CHANGED.value,
            data={"vid": verification.vid},
        ))
