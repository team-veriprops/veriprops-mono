"""Task service (PRD §2.2, §4.1, §4.2, §6, §7.2).

Owns task instantiation at PAID (respecting §4.2 dependency locks), admin
assignment/reassignment, the broadcast pool, and the derivation-owner integration:
after any task mutation it recomputes the global verification status via
``derive_status`` and persists it once (§4.1). Agent-facing accept/decline/submit
build on this in S11; the timeout sweeps that reclaim stalled tasks live here too.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.realtime import VerificationEventType
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.dependencies import is_unlocked, roles_for_tier
from main.app.core.state.derive import derive_status
from main.app.core.state.machine import task_state_machine
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.models import UpdateVerificationDto, Verification
from main.app.domain.verification.task.evidence.service import EvidenceService
from main.app.domain.verification.task.models import (
    AgentDashboardDto,
    CreateTaskDto,
    TaskAssignmentMode,
    UpdateTaskDto,
    VerificationTask,
)
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.app.domain.verification.task.validator import validate_submission
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class VerificationTaskService:
    def __init__(
        self,
        task_repo: VerificationTaskRepo,
        verification_repo: VerificationRepo,
        evidence_service: EvidenceService,
        user_service: UserService,
        audit_service: AuditLogService,
    ):
        self._repo = task_repo
        self._verification_repo = verification_repo
        self._evidence = evidence_service
        self._user_service = user_service
        self._audit = audit_service

    # ── Instantiation (§4.2 dependency-aware) ─────────────────────

    async def instantiate_unlocked(self, verification_id: str) -> List[VerificationTask]:
        """Create ``PENDING`` rows for every tier role that is unlocked and not yet
        instantiated. Dependency-blocked roles (Premium Lawyer before its siblings
        SUBMITTED, §4.2) are skipped until they unlock — so they never appear in the
        derived-state task set early (§2.5). Idempotent: re-running never duplicates.
        """
        verification = await self._get_verification(verification_id)
        tier = VerificationTier(verification.tier)
        existing = {t.role for t in await self._repo.list_for_verification(verification_id)}
        submitted_roles = await self._submitted_roles(verification_id)

        created: List[VerificationTask] = []
        for role in roles_for_tier(tier):
            if role.value in existing:
                continue
            if not is_unlocked(tier, role, submitted_roles):
                continue
            task = await self._repo.create_return_model(CreateTaskDto(
                verification_id=verification_id,
                role=role,
                tier=tier,
                state=TaskState.PENDING,
            ))
            created.append(task)
        return created

    async def broadcast_unassigned(self, verification_id: str) -> List[VerificationTask]:
        """Put every un-owned PENDING task into the open pool (§6.2 auto-assignment).

        First-accept-wins is enforced on the agent accept path (S11); here we only
        open the pool and set the starvation timeout (§7.2).
        """
        pool_expires = Utils.datetime_now() + timedelta(hours=settings.TASK_POOL_TIMEOUT_HOURS)
        broadcast: List[VerificationTask] = []
        for task in await self._repo.list_for_verification(verification_id):
            if task.state == TaskState.PENDING.value and not task.assigned_agent_id:
                await self._repo.update(task.id, UpdateTaskDto(
                    in_pool=True,
                    assignment_mode=TaskAssignmentMode.BROADCAST.value,
                ))
                await self._set_pool_expiry(task.id, pool_expires)
                broadcast.append(task)
        return broadcast

    async def prepare_for_paid(self, verification_id: str) -> None:
        """At PAID: instantiate unlocked tasks and, when auto-assignment is enabled,
        broadcast them to the pool (§6.2). Manual assignment is always available."""
        await self.instantiate_unlocked(verification_id)
        if settings.AUTO_ASSIGNMENT_ENABLED:
            await self.broadcast_unassigned(verification_id)

    # ── Admin assignment (manual path, §6.1/§6.3) ─────────────────

    async def assign(
        self, verification_id: str, role: AgentRole, agent_id: str, admin_id: str
    ) -> VerificationTask:
        """Assign (or reassign) a role's task to a specific agent (§2.2 manual path).

        Enforces ``agent_max_active_tasks`` (§6.5), transitions the task to ASSIGNED,
        takes it out of the pool, and re-derives the verification status (first
        assignment moves PAID → IN_PROGRESS via the derivation owner, §6.3)."""
        verification = await self._get_verification(verification_id)
        if verification.status in (
            VerificationStatus.CANCELLED.value,
            VerificationStatus.REFUNDED.value,
            VerificationStatus.FAILED.value,
        ):
            raise InvalidResourceStateException(
                resource="verification",
                message="This verification is in a terminal state.",
            )

        await self._assert_capacity(agent_id)

        task = await self._repo.get_by_role(verification_id, role.value)
        if task is None:
            tier = VerificationTier(verification.tier)
            if not is_unlocked(tier, role, await self._submitted_roles(verification_id)):
                raise InvalidResourceStateException(
                    resource="task",
                    message=f"The {role.value} task is still locked by its dependencies.",
                )
            task = await self._repo.create_return_model(CreateTaskDto(
                verification_id=verification_id, role=role, tier=tier, state=TaskState.PENDING,
            ))

        reassignment = task.assigned_agent_id is not None and task.assigned_agent_id != agent_id
        self._assert_task_transition(task.state, TaskState.ASSIGNED)
        await self._repo.update(task.id, UpdateTaskDto(
            state=TaskState.ASSIGNED.value,
            assigned_agent_id=agent_id,
            assignment_mode=TaskAssignmentMode.MANUAL.value,
            in_pool=False,
        ))
        await self._set_assign_timestamps(task.id)

        self._audit.schedule(
            action=AuditActionType.TASK_REASSIGNED if reassignment else AuditActionType.TASK_ASSIGNED,
            resource_type="verification_task",
            resource_id=task.id,
            actor_id=admin_id,
            from_state=task.state,
            to_state=TaskState.ASSIGNED.value,
            details={"verification_id": verification_id, "role": role.value, "agent_id": agent_id},
        )
        await self._derive_and_persist(verification_id, actor_id=admin_id)
        return await self._repo.get_model(task.id)

    # ── Agent task execution (§7.1, §7.3) ─────────────────────────

    async def list_for_agent(
        self, agent_id: str, states: Optional[List[str]], page: int, page_size: int
    ):
        """Assigned/owned tasks for the agent dashboard (paged)."""
        return await self._repo.page_for_agent(
            agent_id, states, offset=page * page_size, limit=page_size
        )

    async def count_pool_pending(self) -> int:
        """Unclaimed broadcast tasks in the open pool (admin dashboard §6.3)."""
        return await self._repo.count_pool_pending()

    async def agent_summary(self, agent_id: str) -> AgentDashboardDto:
        """Agent home rollups (§7): the agent's own tasks counted by state, server-side."""
        raw = await self._repo.count_by_state_for_agent(agent_id)
        state_counts = {TaskState(s): c for s, c in raw.items()}
        active = sum(raw.get(s, 0) for s in (
            TaskState.ACCEPTED.value, TaskState.IN_PROGRESS.value, TaskState.REJECTED.value,
        ))
        return AgentDashboardDto(
            assigned=raw.get(TaskState.ASSIGNED.value, 0),
            active=active,
            submitted=raw.get(TaskState.SUBMITTED.value, 0),
            approved=raw.get(TaskState.APPROVED.value, 0),
            total=sum(raw.values()),
            state_counts=state_counts,
        )

    async def accept(self, task_id: str, agent_id: str) -> VerificationTask:
        """Agent accepts a task (§7.1). Broadcast pool = first-accept-wins (the task
        must still be unclaimed PENDING); manual = only the assigned agent may accept.
        Enforces capacity (§6.5) and moves the task to ACCEPTED."""
        task = await self._get_task(task_id)
        if task.state == TaskState.ACCEPTED.value and task.assigned_agent_id == agent_id:
            return task  # idempotent re-accept

        if task.in_pool:
            # First-accept-wins: guard against a second claimant of the same pool task.
            if task.state != TaskState.PENDING.value or task.assigned_agent_id:
                raise InvalidResourceStateException(
                    resource="task", message="This task has already been taken."
                )
        elif task.assigned_agent_id and task.assigned_agent_id != agent_id:
            raise ValidationException(message="This task is assigned to another agent.")

        await self._assert_capacity(agent_id)
        self._assert_task_transition(task.state, TaskState.ACCEPTED)
        await self._repo.update(task.id, UpdateTaskDto(
            state=TaskState.ACCEPTED.value,
            assigned_agent_id=agent_id,
            assignment_mode=task.assignment_mode or TaskAssignmentMode.BROADCAST.value,
            in_pool=False,
        ))
        await self._set_accepted_timestamp(task.id)
        self._audit.schedule(
            action=AuditActionType.TASK_ACCEPTED,
            resource_type="verification_task", resource_id=task.id, actor_id=agent_id,
            from_state=task.state, to_state=TaskState.ACCEPTED.value,
            details={"role": task.role},
        )
        await self._derive_and_persist(task.verification_id, actor_id=agent_id)
        return await self._repo.get_model(task.id)

    async def decline(self, task_id: str, agent_id: str, reason: Optional[str]) -> VerificationTask:
        """Agent declines a task they own (§7.1). Returns it to the open pool for the
        next agent and records the decline (feeds ranking / reliability, §7.2)."""
        task = await self._get_owned_task(task_id, agent_id)
        if task.state not in (TaskState.ASSIGNED.value, TaskState.ACCEPTED.value):
            raise InvalidResourceStateException(
                resource="task", message="Only an assigned/accepted task can be declined."
            )
        self._assert_task_transition(task.state, TaskState.PENDING)
        await self._repo.update(task.id, UpdateTaskDto(
            state=TaskState.PENDING.value,
            in_pool=True,
            decline_count=(task.decline_count or 0) + 1,
        ))
        row = await self._repo.get_model(task.id)
        if row is not None:
            row.assigned_agent_id = None  # NULL — dropped by the exclude_none update path
        self._audit.schedule(
            action=AuditActionType.TASK_DECLINED,
            resource_type="verification_task", resource_id=task.id, actor_id=agent_id,
            from_state=task.state, to_state=TaskState.PENDING.value,
            details={"role": task.role, "reason": reason},
        )
        await self._derive_and_persist(task.verification_id, actor_id=agent_id)
        return await self._repo.get_model(task.id)

    async def start(self, task_id: str, agent_id: str) -> VerificationTask:
        """Agent begins work (§7.3): ACCEPTED → IN_PROGRESS."""
        task = await self._get_owned_task(task_id, agent_id)
        self._assert_task_transition(task.state, TaskState.IN_PROGRESS)
        await self._repo.update(task.id, UpdateTaskDto(state=TaskState.IN_PROGRESS.value))
        self._audit.schedule(
            action=AuditActionType.TASK_STARTED,
            resource_type="verification_task", resource_id=task.id, actor_id=agent_id,
            from_state=task.state, to_state=TaskState.IN_PROGRESS.value,
            details={"role": task.role},
        )
        await self._derive_and_persist(task.verification_id, actor_id=agent_id)
        return await self._repo.get_model(task.id)

    async def add_evidence(
        self, task_id: str, agent_id: str, *, file_bytes: bytes, kind, mime_type=None,
        gps_latitude=None, gps_longitude=None,
    ):
        """Capture a piece of proof-of-work for an in-progress task (§4.5, §7.3a).
        Ownership + IN_PROGRESS enforced; the evidence service stamps hash/GPS/timestamp."""
        task = await self._get_owned_task(task_id, agent_id)
        if task.state != TaskState.IN_PROGRESS.value:
            raise InvalidResourceStateException(
                resource="task", message="Evidence can only be added while the task is in progress."
            )
        item = await self._evidence.capture(
            task_id=task.id, verification_id=task.verification_id, agent_id=agent_id,
            file_bytes=file_bytes, kind=kind, mime_type=mime_type,
            gps_latitude=gps_latitude, gps_longitude=gps_longitude,
        )
        self._audit.schedule(
            action=AuditActionType.EVIDENCE_CAPTURED,
            resource_type="task_evidence", resource_id=item.id, actor_id=agent_id,
            details={"task_id": task.id, "sha256": item.content_sha256, "kind": item.kind},
        )
        # Pure SSE refresh — no customer notification at capture (evidence is only
        # customer-visible after review-approval, D17).
        await publish_domain_event(DomainEvent(
            verification_id=task.verification_id, sse_event=VerificationEventType.TASK_UPDATED.value,
        ))
        return item

    async def submit(self, task_id: str, agent_id: str, payload: dict) -> VerificationTask:
        """Agent submits role findings (§7.3): IN_PROGRESS → SUBMITTED. Requires at least
        one evidence item (proof-of-work). First successful submission upgrades the agent
        to trusted (§3.3). The derive owner promotes the verification to UNDER_REVIEW once
        every required task is SUBMITTED (§2.5)."""
        task = await self._get_owned_task(task_id, agent_id)
        validate_submission(AgentRole(task.role), payload)
        if await self._evidence.count_for_task(task.id) == 0:
            raise ValidationException(
                message="At least one evidence item is required before submitting."
            )
        self._assert_task_transition(task.state, TaskState.SUBMITTED)
        await self._repo.update(task.id, UpdateTaskDto(
            state=TaskState.SUBMITTED.value,
            submission_payload=payload,
        ))
        await self._set_submitted_timestamp(task.id)
        await self._user_service.upgrade_trust_status_if_eligible(agent_id, UserPersona.AGENT)
        self._audit.schedule(
            action=AuditActionType.TASK_SUBMITTED,
            resource_type="verification_task", resource_id=task.id, actor_id=agent_id,
            from_state=task.state, to_state=TaskState.SUBMITTED.value,
            details={"role": task.role},
        )
        await self._derive_and_persist(task.verification_id, actor_id=agent_id)
        return await self._repo.get_model(task.id)

    # ── Timeout sweeps (§7.2) ─────────────────────────────────────

    async def sweep_no_show(self) -> int:
        """Return manually-assigned tasks the agent never accepted in time to PENDING."""
        now = Utils.datetime_now()
        count = 0
        for task in await self._repo.list_accept_deadline_expired(now):
            await self._return_to_pending(task, reason="no_show_timeout")
            count += 1
        return count

    async def sweep_pool_starvation(self) -> int:
        """Aging broadcast tasks unclaimed past the pool timeout escalate off the open
        pool to await targeted assignment by admin/ranking (§7.2 starvation backstop)."""
        now = Utils.datetime_now()
        count = 0
        for task in await self._repo.list_pool_expired(now):
            await self._repo.update(task.id, UpdateTaskDto(in_pool=False))
            if settings.REMOTE_JOB_BONUS_MINOR > 0 and task.remote_bonus_minor is None:
                await self._repo.update(task.id, UpdateTaskDto(
                    remote_bonus_minor=settings.REMOTE_JOB_BONUS_MINOR
                ))
            self._audit.schedule(
                action=AuditActionType.TASK_STATE_CHANGED,
                resource_type="verification_task",
                resource_id=task.id,
                actor_id=None,
                details={"event": "pool_starvation_escalated", "role": task.role},
            )
            count += 1
        return count

    # ── Read ──────────────────────────────────────────────────────

    async def list_for_verification(self, verification_id: str) -> List[VerificationTask]:
        return await self._repo.list_for_verification(verification_id)

    # ── helpers ───────────────────────────────────────────────────

    async def _get_task(self, task_id: str) -> VerificationTask:
        task = await self._repo.get_model(task_id)
        if not task:
            raise ResourceNotFoundException(resource="task")
        return task

    async def _get_owned_task(self, task_id: str, agent_id: str) -> VerificationTask:
        task = await self._get_task(task_id)
        if task.assigned_agent_id != agent_id:
            raise ValidationException(message="This task is not assigned to you.")
        return task

    async def _get_verification(self, verification_id: str) -> Verification:
        verification = await self._verification_repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        if not verification.tier:
            raise InvalidResourceStateException(
                resource="verification", message="Verification has no tier set."
            )
        return verification

    async def _submitted_roles(self, verification_id: str) -> List[AgentRole]:
        tasks = await self._repo.list_for_verification(verification_id)
        settled = {TaskState.SUBMITTED.value, TaskState.APPROVED.value}
        return [AgentRole(t.role) for t in tasks if t.state in settled]

    async def _assert_capacity(self, agent_id: str) -> None:
        active = await self._repo.count_active_for_agent(agent_id)
        if active >= settings.AGENT_MAX_ACTIVE_TASKS:
            raise ValidationException(
                message=f"Agent is at capacity ({settings.AGENT_MAX_ACTIVE_TASKS} active tasks)."
            )

    def _assert_task_transition(self, current: str, target: TaskState) -> None:
        task_state_machine.assert_can_transition(current, target.value, resource="Task")

    async def _return_to_pending(self, task: VerificationTask, reason: str) -> None:
        self._assert_task_transition(task.state, TaskState.PENDING)
        await self._repo.update(task.id, UpdateTaskDto(
            state=TaskState.PENDING.value,
            in_pool=False,
            decline_count=(task.decline_count or 0) + 1,
        ))
        # assigned_agent_id must be cleared to NULL — the update DTO path drops None
        # fields (exclude_none), so set it on the model directly (CLAUDE.md GenericRepo note).
        row = await self._repo.get_model(task.id)
        if row is not None:
            row.assigned_agent_id = None
        self._audit.schedule(
            action=AuditActionType.TASK_STATE_CHANGED,
            resource_type="verification_task",
            resource_id=task.id,
            actor_id=None,
            from_state=task.state,
            to_state=TaskState.PENDING.value,
            details={"event": reason, "role": task.role},
        )
        await self._derive_and_persist(task.verification_id, actor_id=None)

    async def _derive_and_persist(self, verification_id: str, actor_id: Optional[str]) -> None:
        """The §4.1 derivation-owner integration: recompute the global status from the
        task set and persist it once, auditing any change. The only place a task
        mutation writes ``verification.status``."""
        verification = await self._verification_repo.get_model(verification_id)
        if not verification:
            return
        task_states = [t.state for t in await self._repo.list_for_verification(verification_id)]
        new_status = derive_status(verification.status, task_states)
        # A generic "something on this verification changed" push (§4.9). The frontend
        # re-reads the authoritative snapshot on any event, so this covers task moves
        # that don't shift the global status too. Pure SSE nudge — no notification.
        await publish_domain_event(DomainEvent(
            verification_id=verification_id, sse_event=VerificationEventType.TASK_UPDATED.value,
        ))
        if new_status.value == verification.status:
            return
        await self._verification_repo.update(
            verification_id, UpdateVerificationDto(status=new_status.value)
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="verification",
            resource_id=verification_id,
            actor_id=actor_id,
            from_state=verification.status,
            to_state=new_status.value,
        )
        # One publish (§4.8): SSE re-emit + customer status-change notification (§12.2).
        await publish_domain_event(DomainEvent(
            type=EventType.STATUS_CHANGED, verification_id=verification_id,
            recipient_user_ids=(verification.customer_id,),
            sse_event=VerificationEventType.STATUS_CHANGED.value,
            data={"status": new_status.value},
        ))

    async def _set_pool_expiry(self, task_id: str, expires_at) -> None:
        # datetime fields are set on the model, not via the json-encoding update path.
        task = await self._repo.get_model(task_id)
        task.pool_expires_at = expires_at

    async def _set_assign_timestamps(self, task_id: str) -> None:
        task = await self._repo.get_model(task_id)
        now = Utils.datetime_now()
        task.assigned_at = now
        task.accept_deadline_at = now + timedelta(hours=settings.TASK_NO_SHOW_TIMEOUT_HOURS)

    async def _set_accepted_timestamp(self, task_id: str) -> None:
        task = await self._repo.get_model(task_id)
        task.accepted_at = Utils.datetime_now()

    async def _set_submitted_timestamp(self, task_id: str) -> None:
        task = await self._repo.get_model(task_id)
        task.submitted_at = Utils.datetime_now()
