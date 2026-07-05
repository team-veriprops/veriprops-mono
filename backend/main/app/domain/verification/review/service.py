"""Admin review & report release service (PRD §8).

The release gate. Admin reviews each role submission (approve records intent + a quality
score; reject sends the task back to rework). The verification only reaches COMPLETED via
an explicit ``release``, which flips the reviewed tasks SUBMITTED→APPROVED atomically (so
the derive owner projects COMPLETED exactly at release, never before), accrues agent
commissions (§15.2/D13), computes the composite trust score from the admin weights (§8.3),
and produces the versioned RELEASED report (§8.6). Reopen supersedes the report and sends a
task back to work; fail marks FAILED and refunds (§8.5).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.realtime import VerificationEventType
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.dependencies import required_task_count, roles_for_tier
from main.app.core.state.derive import derive_status
from main.app.core.state.machine import task_state_machine
from main.app.core.state.status import (
    AgentRole,
    ReportRevisionKind,
    TaskState,
    VerificationStatus,
    VerificationTier,
)
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.models import CreateCommissionDto
from main.app.domain.commission.service import CommissionService
from main.app.domain.message.verification_messages import VerificationMessages
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.models import UpdateVerificationDto, Verification
from main.app.domain.verification.report.service import ReportService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.review.conflict import ReviewConflict, detect_conflicts
from main.app.domain.verification.scoring.service import TrustScoreWeightService
from main.app.domain.verification.task.models import UpdateTaskDto, VerificationTask
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_APPROVED_REVIEW = "APPROVED"
_REJECTED_REVIEW = "REJECTED"


def _release_ready(task) -> bool:
    """A task is ready to (re-)release when it is already APPROVED (untouched since the last
    release — e.g. a partial re-check reopened only some tasks, §14.1) or it is SUBMITTED and
    admin review-approved. First release: every task is SUBMITTED+approved; re-release: a mix."""
    if task.state == TaskState.APPROVED.value:
        return True
    return task.state == TaskState.SUBMITTED.value and task.review_decision == _APPROVED_REVIEW


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReviewService:
    def __init__(
        self,
        task_repo: VerificationTaskRepo,
        verification_repo: VerificationRepo,
        report_service: ReportService,
        weight_service: TrustScoreWeightService,
        commission_service: CommissionService,
        payment_service: PaymentService,
        verification_messages: VerificationMessages,
        audit_service: AuditLogService,
    ):
        self._tasks = task_repo
        self._verification_repo = verification_repo
        self._reports = report_service
        self._weights = weight_service
        self._commissions = commission_service
        self._payments = payment_service
        self._messages = verification_messages
        self._audit = audit_service

    # ── Per-task review (§8.1) ────────────────────────────────────

    async def approve_task(
        self, verification_id: str, role: AgentRole, quality: int, admin_id: str,
        interim_note: Optional[str] = None,
    ) -> VerificationTask:
        """Record admin approval + a quality score. The task stays SUBMITTED — it only
        transitions to APPROVED at explicit release, so nothing auto-completes (§8).

        ``interim_note`` is an optional one-line reassurance shown to the customer once
        approved (§9.3) — captured here so a positive milestone is delivered with context.
        """
        if not 0 <= quality <= 100:
            raise ValidationException(message="Quality score must be between 0 and 100.")
        task = await self._get_task(verification_id, role)
        if task.state != TaskState.SUBMITTED.value:
            raise InvalidResourceStateException(
                resource="task", message="Only a submitted task can be approved."
            )
        await self._tasks.update(task.id, UpdateTaskDto(
            review_decision=_APPROVED_REVIEW, review_quality=quality,
            interim_note=interim_note,
        ))
        self._audit.schedule(
            action=AuditActionType.TASK_APPROVED,
            resource_type="verification_task", resource_id=task.id, actor_id=admin_id,
            details={"role": role.value, "quality": quality},
        )
        # Approval records intent without a state change, so it never reaches
        # _derive_and_persist — push a refresh signal here so the customer's interim
        # reassurance milestone (§9.3) surfaces live once admin review-approves. Pure SSE
        # nudge (no notification): a typed event is not needed.
        await publish_domain_event(DomainEvent(
            verification_id=verification_id, sse_event=VerificationEventType.TASK_UPDATED.value,
        ))
        return await self._tasks.get_model(task.id)

    async def reject_task(
        self, verification_id: str, role: AgentRole, reason: str, admin_id: str
    ) -> VerificationTask:
        """Reject a submission → back to rework (SUBMITTED→REJECTED; derive → IN_PROGRESS)."""
        task = await self._get_task(verification_id, role)
        task_state_machine.assert_can_transition(
            task.state, TaskState.REJECTED.value, resource="Task"
        )
        await self._tasks.update(task.id, UpdateTaskDto(
            state=TaskState.REJECTED.value, review_decision=_REJECTED_REVIEW, rejection_reason=reason,
        ))
        self._audit.schedule(
            action=AuditActionType.TASK_REJECTED,
            resource_type="verification_task", resource_id=task.id, actor_id=admin_id,
            from_state=task.state, to_state=TaskState.REJECTED.value,
            details={"role": role.value, "reason": reason},
        )
        # A rejection reason auto-posts to the admin↔agent thread, tagged to that task (§11.1).
        await self._auto_post_rejection(verification_id, task, role, reason)
        # Notify the agent of the revision request (§12.2 agent) — in-app + email, one publish.
        if task.assigned_agent_id:
            await publish_domain_event(DomainEvent(
                type=EventType.TASK_REJECTED, verification_id=verification_id,
                recipient_user_ids=(task.assigned_agent_id,),
                data={"role": role.value, "reason": reason},
            ))
        await self._derive_and_persist(verification_id, admin_id)
        return await self._tasks.get_model(task.id)

    async def _auto_post_rejection(
        self, verification_id: str, task, role: AgentRole, reason: str
    ) -> None:
        """Best-effort system auto-post of the revision instructions (§11.1). Resolved lazily
        so the review service never hard-depends on the communication layer; a comms failure
        must never break the rejection transaction."""
        try:
            from kink import di
            from main.app.domain.communication.service import CommunicationService

            comms = di[CommunicationService]
            await comms.auto_post_agent(
                verification_id,
                task.assigned_agent_id,
                f"Revision requested for the {role.value.title()} task: {reason}",
                task_id=task.id,
            )
        except Exception:  # noqa: BLE001 — auto-post is best-effort, never fatal
            pass

    # ── Release gate (§8.3, §8.6) ─────────────────────────────────

    async def release(
        self, verification_id: str, admin_id: str, reason: Optional[str] = None
    ) -> ReviewContext:
        """Explicit release (§8): all required tasks must be SUBMITTED + review-approved and
        free of unresolved HIGH conflicts. Flips them to APPROVED, accrues commissions, computes
        the composite score, and produces the versioned RELEASED report; derive → COMPLETED."""
        verification = await self._get_verification(verification_id)
        if verification.status != VerificationStatus.UNDER_REVIEW.value:
            raise InvalidResourceStateException(
                resource="verification", message="Only a verification under review can be released."
            )
        tier = VerificationTier(verification.tier)
        tasks = await self._tasks.list_for_verification(verification_id)

        if len(tasks) != required_task_count(tier):
            raise ValidationException(message="Not all required tasks are present.")
        for t in tasks:
            if not _release_ready(t):
                raise ValidationException(
                    message=f"The {t.role} task is not review-approved yet."
                )

        submissions = self._submissions_by_role(tasks)
        conflicts = detect_conflicts(submissions)
        if any(c.severity == "HIGH" for c in conflicts):
            raise ValidationException(
                message="Unresolved high-severity conflicts — reject the affected task(s) first."
            )

        # Flip every reviewed task to APPROVED, then derive once → COMPLETED.
        for t in tasks:
            task_state_machine.assert_can_transition(
                t.state, TaskState.APPROVED.value, resource="Task"
            )
            await self._tasks.update(t.id, UpdateTaskDto(state=TaskState.APPROVED.value))
            await self._set_approved_at(t.id)

        role_quality = {AgentRole(t.role): (t.review_quality or 100) for t in tasks}
        composite = await self._weights.compute_composite(tier, role_quality)

        await self._accrue_commissions(verification, tasks)
        # A re-check / tier-upgrade cycle records why this release bumps the version (§14).
        revision_kind = (
            ReportRevisionKind(verification.pending_revision_kind)
            if verification.pending_revision_kind else ReportRevisionKind.INITIAL
        )
        report = await self._reports.release(
            verification_id=verification_id, findings=submissions_as_json(submissions),
            composite_trust_score=composite, released_by=admin_id, reason=reason,
            revision_kind=revision_kind,
        )
        if verification.pending_revision_kind:
            # Clear to NULL on the model — the update DTO path drops None (exclude_none).
            row = await self._verification_repo.get_model(verification_id)
            if row is not None:
                row.pending_revision_kind = None
        await self._derive_and_persist(verification_id, admin_id)
        # One publish (§4.8): the realtime subscriber re-emits the report-released SSE and the
        # notification subscriber fans out the "report ready" in-app + email/SMS (§10, §12.2) —
        # replacing the previous direct send_report_ready call (D20).
        await publish_domain_event(DomainEvent(
            type=EventType.REPORT_READY, verification_id=verification_id,
            recipient_user_ids=(verification.customer_id,),
            sse_event=VerificationEventType.REPORT_RELEASED.value,
            data={"version": report.report_version, "trustScore": composite},
        ))
        return ReviewContext(report=report, trust_score=composite, conflicts=conflicts)

    async def reopen_task(
        self, verification_id: str, role: AgentRole, admin_id: str
    ) -> VerificationTask:
        """Reopen an APPROVED task after release (§8.4): APPROVED→IN_PROGRESS. Supersedes the
        live report; derive → IN_PROGRESS."""
        task = await self._get_task(verification_id, role)
        task_state_machine.assert_can_transition(
            task.state, TaskState.IN_PROGRESS.value, resource="Task"
        )
        await self._tasks.update(task.id, UpdateTaskDto(
            state=TaskState.IN_PROGRESS.value, review_decision=None,
        ))
        await self._reports.supersede_current(verification_id, admin_id)
        self._audit.schedule(
            action=AuditActionType.TASK_REOPENED,
            resource_type="verification_task", resource_id=task.id, actor_id=admin_id,
            from_state=task.state, to_state=TaskState.IN_PROGRESS.value,
            details={"role": role.value},
        )
        await self._derive_and_persist(verification_id, admin_id)
        return await self._tasks.get_model(task.id)

    async def fail(self, verification_id: str, reason: str, admin_id: str) -> Verification:
        """Fail the verification and refund the customer (§8.5)."""
        verification = await self._get_verification(verification_id)
        from main.app.core.state.machine import verification_state_machine
        verification_state_machine.assert_can_transition(
            verification.status, VerificationStatus.FAILED.value, resource="Verification"
        )
        await self._verification_repo.update(
            verification_id, UpdateVerificationDto(status=VerificationStatus.FAILED.value)
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_FAILED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
            from_state=verification.status, to_state=VerificationStatus.FAILED.value,
            details={"reason": reason},
        )
        refunded = await self._payments.refund(verification_id, admin_id, reason)
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_REFUNDED,
            resource_type="verification", resource_id=verification_id, actor_id=admin_id,
            details={"refunded_minor": refunded, "reason": reason},
        )
        return await self._verification_repo.get_model(verification_id)

    # ── Read (§8.1) ───────────────────────────────────────────────

    async def get_review_context(self, verification_id: str) -> ReviewContext:
        verification = await self._get_verification(verification_id)
        tier = VerificationTier(verification.tier) if verification.tier else None
        tasks = await self._tasks.list_for_verification(verification_id)
        submissions = self._submissions_by_role(tasks)
        conflicts = detect_conflicts(submissions)

        all_approved = bool(tasks) and all(_release_ready(t) for t in tasks) and (
            tier is not None and len(tasks) == required_task_count(tier)
        )

        projected = None
        if tier and all_approved:
            role_quality = {AgentRole(t.role): (t.review_quality or 100) for t in tasks}
            projected = await self._weights.compute_composite(tier, role_quality)

        report = await self._reports.get_released(verification_id)
        return ReviewContext(
            verification=verification, tier=tier, tasks=tasks, conflicts=conflicts,
            all_approved=all_approved, projected_trust_score=projected,
            releasable=all_approved and not any(c.severity == "HIGH" for c in conflicts)
            and verification.status == VerificationStatus.UNDER_REVIEW.value,
            report=report, submissions=submissions,
        )

    # ── helpers ───────────────────────────────────────────────────

    async def _accrue_commissions(self, verification: Verification, tasks: List[VerificationTask]) -> None:
        """Accrue a CLEARING commission per approved task = price × weight × agent share (D13)."""
        price = verification.price_locked_minor or 0
        if price <= 0:
            return
        tier = VerificationTier(verification.tier)
        weights = {AgentRole(w.role): w.weight_percent for w in await self._weights.list_for_tier(tier)}
        for t in tasks:
            if not t.assigned_agent_id:
                continue
            weight = weights.get(AgentRole(t.role), 0)
            amount = int(price * (weight / 100) * settings.AGENT_COMMISSION_SHARE)
            if amount <= 0:
                continue
            await self._commissions.accrue(CreateCommissionDto(
                verification_id=verification.id, task_id=t.id, agent_id=t.assigned_agent_id,
                role=AgentRole(t.role), tier=tier, amount_minor=amount,
            ))

    def _submissions_by_role(
        self, tasks: List[VerificationTask]
    ) -> Dict[AgentRole, Optional[Dict[str, Any]]]:
        return {AgentRole(t.role): t.submission_payload for t in tasks}

    async def _get_task(self, verification_id: str, role: AgentRole) -> VerificationTask:
        task = await self._tasks.get_by_role(verification_id, role.value)
        if task is None:
            raise ResourceNotFoundException(resource="task")
        return task

    async def _get_verification(self, verification_id: str) -> Verification:
        verification = await self._verification_repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        return verification

    async def _set_approved_at(self, task_id: str) -> None:
        task = await self._tasks.get_model(task_id)
        task.approved_at = Utils.datetime_now()

    async def _derive_and_persist(self, verification_id: str, actor_id: Optional[str]) -> None:
        verification = await self._verification_repo.get_model(verification_id)
        if not verification:
            return
        task_states = [t.state for t in await self._tasks.list_for_verification(verification_id)]
        new_status = derive_status(verification.status, task_states)
        if new_status.value == verification.status:
            return
        await self._verification_repo.update(
            verification_id, UpdateVerificationDto(status=new_status.value)
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="verification", resource_id=verification_id, actor_id=actor_id,
            from_state=verification.status, to_state=new_status.value,
        )
        # One publish (§4.8): SSE re-emit + customer status-change notification (§12.2).
        await publish_domain_event(DomainEvent(
            type=EventType.STATUS_CHANGED, verification_id=verification_id,
            recipient_user_ids=(verification.customer_id,),
            sse_event=VerificationEventType.STATUS_CHANGED.value,
            data={"status": new_status.value},
        ))


class ReviewContext:
    """Lightweight carrier for review results (not a DTO — mapped in the controller)."""

    def __init__(
        self, *, verification=None, tier=None, tasks=None, conflicts: List[ReviewConflict] = None,
        all_approved: bool = False, projected_trust_score: Optional[int] = None,
        releasable: bool = False, report=None, submissions=None, trust_score: Optional[int] = None,
    ):
        self.verification = verification
        self.tier = tier
        self.tasks = tasks or []
        self.conflicts = conflicts or []
        self.all_approved = all_approved
        self.projected_trust_score = projected_trust_score if trust_score is None else trust_score
        self.releasable = releasable
        self.report = report
        self.submissions = submissions or {}


def submissions_as_json(submissions: Dict[AgentRole, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Snapshot the per-role findings into a plain JSON dict for the report."""
    return {role.value: payload for role, payload in submissions.items()}
