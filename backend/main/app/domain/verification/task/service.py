"""Task service — competitive pool assignment, OL accept, role-specific submit.

S19 (pool assignment), S21 (agent accept/decline), S22–S25 (role submit),
S27 (trust elevation).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from kink import di, inject

from main.app.domain.admin_config.service import AdminConfigService
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.agent.models import (
    AgentApplicationStatus,
    AgentQualityScoreDto,
    AvailabilityStatus,
    CreateAgentQualityScoreDto,
    CreateQualityScoreDto,
    UpdateAgentApplicationDto,
)
from main.app.domain.user.agent.repo import AgentApplicationRepo, AgentQualityScoreRepo
from main.app.domain.user.models import TrustStatus, UpdateUserDto
from main.app.domain.user.repo import UserRepo
from main.app.domain.verification.models import UpdateVerificationDto, VerificationStatus
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.models import (
    AvailableAgentDto,
    CreateTaskAssignmentDto,
    CreateTaskDto,
    Task,
    TaskAssignment,
    TaskAssignmentDto,
    TaskDto,
    TaskRole,
    TaskStatus,
    TIER_ROLES,
    UpdateTaskDto,
)
from main.app.domain.verification.task.evidence.repo import EvidenceItemRepo
from main.app.domain.verification.task.repo import TaskAssignmentRepo, TaskRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TaskService:
    def __init__(
        self,
        task_repo: TaskRepo,
        assignment_repo: TaskAssignmentRepo,
        evidence_repo: EvidenceItemRepo,
        verification_repo: VerificationRepo,
        agent_app_repo: AgentApplicationRepo,
        user_repo: UserRepo,
        audit: AuditLogService,
        quality_score_repo: AgentQualityScoreRepo,
        admin_config: AdminConfigService,
    ):
        self._tasks = task_repo
        self._assignments = assignment_repo
        self._evidence = evidence_repo
        self._verifications = verification_repo
        self._agent_apps = agent_app_repo
        self._users = user_repo
        self._audit = audit
        self._quality_scores = quality_score_repo
        self._config = admin_config

    # ── Task creation ─────────────────────────────────────────────────

    async def create_tasks_for_tier(
        self,
        verification_id: str,
        tier: str,
        release_immediately: bool = True,
    ) -> List[TaskDto]:
        """Create one Task per role required by the tier.

        If release_immediately is False, tasks stay PENDING with pool_released_at=None
        (admin must manually release them).  If True, sets pool_released_at=now so
        qualifying agents can see them immediately.
        """
        roles = TIER_ROLES.get(tier.upper(), [])
        now = datetime.now(timezone.utc) if release_immediately else None
        created: List[TaskDto] = []
        for role in roles:
            task = await self._tasks.create_return_model(
                CreateTaskDto(
                    verification_id=verification_id,
                    role=role,
                    status=TaskStatus.PENDING,
                    pool_released_at=now,
                )
            )
            created.append(self._task_to_dto(task))
        # Notify customer that agents have been assigned
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            ver = await self._verifications.get_model(verification_id)
            if ver:
                notif_svc: NotificationService = di[NotificationService]
                await notif_svc.emit(
                    NotificationEvent.AGENTS_ASSIGNED,
                    recipient_id=str(ver.customer_id),
                    context={},
                    entity_type="Verification",
                    entity_id=verification_id,
                )
        except Exception as exc:
            logger.warning(f"Notification emit failed (agents_assigned): {exc}")
        return created

    async def release_to_pool(self, verification_id: str, admin_id: str) -> List[TaskDto]:
        """Release all PENDING tasks for this verification into the agent pool."""
        tasks = await self._tasks.list_for_verification(verification_id)
        now = datetime.now(timezone.utc)
        updated: List[TaskDto] = []
        for task in tasks:
            if task.status == TaskStatus.PENDING.value and task.pool_released_at is None:
                await self._tasks.update(
                    str(task.id),
                    UpdateTaskDto(pool_released_at=now),
                )
                task.pool_released_at = now
            updated.append(self._task_to_dto(task))
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=verification_id,
            actor_id=admin_id,
            meta={"action": "RELEASE_TO_POOL"},
        )
        return updated

    # ── Admin assignment ──────────────────────────────────────────────

    async def admin_assign(
        self, task_id: str, agent_id: str, assigned_by: str,
    ) -> TaskDto:
        """Admin direct-assign — bypasses the pool (task goes to ASSIGNED state)."""
        task = await self._get_task_or_raise(task_id)
        if task.status not in (TaskStatus.PENDING.value, TaskStatus.ASSIGNED.value):
            raise ValidationException(
                message=f"Task cannot be assigned from status {task.status}"
            )
        await self._tasks.update(
            task_id,
            UpdateTaskDto(status=TaskStatus.ASSIGNED, agent_id=agent_id),
        )
        await self._assignments.create_return_model(
            CreateTaskAssignmentDto(
                task_id=task_id,
                agent_id=agent_id,
                assigned_by=assigned_by,
            )
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=assigned_by,
            from_state=task.status,
            to_state=TaskStatus.ASSIGNED.value,
            meta={"action": "ADMIN_ASSIGN", "agent_id": agent_id},
        )
        await self._derive_and_update_verification_status(task.verification_id)
        return self._task_to_dto(await self._tasks.get_task(task_id))

    async def admin_reassign(
        self,
        task_id: str,
        new_agent_id: str,
        assigned_by: str,
        note: Optional[str] = None,
    ) -> TaskDto:
        """Admin reassign — moves an active task to a different agent."""
        task = await self._get_task_or_raise(task_id)
        reassignable_statuses = {
            TaskStatus.ASSIGNED.value,
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
        }
        if task.status not in reassignable_statuses:
            raise ValidationException(
                message=f"Task cannot be reassigned from status {task.status}"
            )
        old_agent_id = task.agent_id
        await self._tasks.update(
            task_id,
            UpdateTaskDto(
                status=TaskStatus.ASSIGNED,
                agent_id=new_agent_id,
                accepted_at=None,
            ),
        )
        await self._assignments.create_return_model(
            CreateTaskAssignmentDto(
                task_id=task_id,
                agent_id=new_agent_id,
                assigned_by=assigned_by,
                reassigned_from_id=old_agent_id,
                note=note,
            )
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=assigned_by,
            from_state=task.status,
            to_state=TaskStatus.ASSIGNED.value,
            meta={
                "action": "ADMIN_REASSIGN",
                "from_agent_id": old_agent_id,
                "to_agent_id": new_agent_id,
                "note": note,
            },
        )
        await self._derive_and_update_verification_status(task.verification_id)
        return self._task_to_dto(await self._tasks.get_task(task_id))

    # ── Agent actions ─────────────────────────────────────────────────

    async def agent_accept(self, task_id: str, agent_id: str) -> TaskDto:
        """Competitive pool accept — first agent to call this wins (OL).

        Raises ResourceConflictException if another agent already accepted.
        """
        task = await self._get_task_or_raise(task_id)
        # Admin-assigned path: agent_id must match and status must be ASSIGNED.
        if task.status == TaskStatus.ASSIGNED.value:
            if task.agent_id != agent_id:
                raise ValidationException(message="This task is not assigned to you")
            await self._tasks.update(
                task_id,
                UpdateTaskDto(
                    status=TaskStatus.ACCEPTED,
                    accepted_at=datetime.now(timezone.utc),
                ),
            )
        elif task.status == TaskStatus.PENDING.value:
            # Pool path: atomic optimistic-lock claim
            claimed = await self._tasks.claim_task(task_id, agent_id)
            if not claimed:
                raise ResourceConflictException(
                    resource="Task",
                    message="Another agent accepted this job",
                )
        else:
            raise ValidationException(
                message=f"Task cannot be accepted from status {task.status}"
            )
        await self._assignments.create_return_model(
            CreateTaskAssignmentDto(task_id=task_id, agent_id=agent_id)
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=agent_id,
            from_state=task.status,
            to_state=TaskStatus.ACCEPTED.value,
            meta={"action": "AGENT_ACCEPT"},
        )
        await self._derive_and_update_verification_status(task.verification_id)
        await self._maybe_flip_unavailable(agent_id)
        return self._task_to_dto(await self._tasks.get_task(task_id))

    async def agent_decline(self, task_id: str, agent_id: str) -> TaskDto:
        """Agent declines — returns ACCEPTED task back to pool (PENDING)."""
        task = await self._get_task_or_raise(task_id)
        if task.status != TaskStatus.ACCEPTED.value:
            raise ValidationException(
                message="Only ACCEPTED tasks can be declined"
            )
        if task.agent_id != agent_id:
            raise ValidationException(message="This task is not assigned to you")
        await self._tasks.update(
            task_id,
            UpdateTaskDto(
                status=TaskStatus.PENDING,
                agent_id=None,
                accepted_at=None,
            ),
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=agent_id,
            from_state=TaskStatus.ACCEPTED.value,
            to_state=TaskStatus.PENDING.value,
            meta={"action": "AGENT_DECLINE"},
        )
        await self._derive_and_update_verification_status(task.verification_id)
        await self._maybe_restore_availability(agent_id)
        return self._task_to_dto(await self._tasks.get_task(task_id))

    async def save_draft(
        self, task_id: str, agent_id: str, payload: Dict[str, Any],
    ) -> TaskDto:
        """Persist a draft payload for an in-progress task (autosave / S26)."""
        task = await self._get_task_or_raise(task_id)
        if task.agent_id != agent_id:
            raise ValidationException(message="This task is not assigned to you")
        active_statuses = {
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
        }
        if task.status not in active_statuses:
            raise ValidationException(
                message="Draft can only be saved for active tasks"
            )
        if task.status == TaskStatus.ACCEPTED.value:
            # First save marks task as IN_PROGRESS
            await self._tasks.update(
                task_id,
                UpdateTaskDto(
                    status=TaskStatus.IN_PROGRESS,
                    draft_payload=json.dumps(payload),
                ),
            )
        else:
            await self._tasks.update(
                task_id,
                UpdateTaskDto(draft_payload=json.dumps(payload)),
            )
        return self._task_to_dto(await self._tasks.get_task(task_id))

    async def submit(
        self, task_id: str, agent_id: str, payload: Dict[str, Any],
    ) -> TaskDto:
        """Role-specific submit with validation and state derivation."""
        task = await self._get_task_or_raise(task_id)
        if task.agent_id != agent_id:
            raise ValidationException(message="This task is not assigned to you")
        active_statuses = {TaskStatus.ACCEPTED.value, TaskStatus.IN_PROGRESS.value}
        if task.status not in active_statuses:
            raise ValidationException(
                message=f"Task cannot be submitted from status {task.status}"
            )
        await self._validate_submit_payload(TaskRole(task.role), payload, task)
        now = datetime.now(timezone.utc)
        await self._tasks.update(
            task_id,
            UpdateTaskDto(
                status=TaskStatus.SUBMITTED,
                submitted_at=now,
                draft_payload=json.dumps(payload),
            ),
        )
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Task",
            resource_id=task_id,
            actor_id=agent_id,
            from_state=task.status,
            to_state=TaskStatus.SUBMITTED.value,
            meta={"action": "AGENT_SUBMIT", "role": task.role},
        )
        await self._maybe_elevate_trust(agent_id)
        await self._derive_and_update_verification_status(task.verification_id)
        return self._task_to_dto(await self._tasks.get_task(task_id))

    async def list_for_verification(self, verification_id: str) -> List[TaskDto]:
        tasks = await self._tasks.list_for_verification(verification_id)
        return [self._task_to_dto(t) for t in tasks]

    async def get_task(self, task_id: str) -> TaskDto:
        task = await self._get_task_or_raise(task_id)
        return self._task_to_dto(task)

    # ── Agent query helpers ───────────────────────────────────────────

    async def list_available_for_agent(
        self,
        agent_id: str,
        role: str,
        state: Optional[str] = None,
    ) -> List[TaskDto]:
        tasks = await self._tasks.list_pending_for_agent(role=role, state=state)
        # Filter out tasks with no pool_released_at (held for manual assignment)
        return [
            self._task_to_dto(t)
            for t in tasks
            if t.pool_released_at is not None
        ]

    async def list_active_for_agent(self, agent_id: str) -> List[TaskDto]:
        tasks = await self._tasks.list_active_for_agent(agent_id)
        return [self._task_to_dto(t) for t in tasks]

    async def list_completed_for_agent(self, agent_id: str) -> List[TaskDto]:
        tasks = await self._tasks.list_completed_for_agent(agent_id)
        return [self._task_to_dto(t) for t in tasks]

    # ── Quality scores (Phase 16 — S49) ──────────────────────────────

    async def assign_quality_score(
        self,
        task_id: str,
        dto: CreateQualityScoreDto,
        admin_id: str,
    ) -> AgentQualityScoreDto:
        """Admin assigns 1–5 quality score after a task is APPROVED."""
        task = await self._get_task_or_raise(task_id)
        if task.status != TaskStatus.APPROVED.value:
            raise ValidationException(
                message="Quality scores can only be assigned to APPROVED tasks"
            )
        if not (1 <= dto.score <= 5):
            raise ValidationException(message="Quality score must be between 1 and 5")

        # Upsert — overwrite if admin is correcting a score
        existing = await self._quality_scores.get_by_task_id(task_id)
        if existing:
            from main.app.domain.user.agent.models import UpdateAgentQualityScoreDto
            await self._quality_scores.update(str(existing.id), UpdateAgentQualityScoreDto(
                score=dto.score,
                note=dto.note,
                reviewed_by_admin_id=admin_id,
            ))
            row = await self._quality_scores.get_by_task_id(task_id)
        else:
            row = await self._quality_scores.create_return_model(CreateAgentQualityScoreDto(
                task_id=task_id,
                agent_id=task.agent_id,
                score=dto.score,
                note=dto.note,
                reviewed_by_admin_id=admin_id,
            ))
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="AgentQualityScore",
            resource_id=task_id,
            actor_id=admin_id,
            meta={"score": dto.score, "agent_id": task.agent_id},
        )
        return AgentQualityScoreDto(
            id=str(row.id),
            task_id=row.task_id,
            agent_id=row.agent_id,
            score=row.score,
            note=row.note,
            reviewed_by_admin_id=row.reviewed_by_admin_id,
            date_created=row.date_created,
        )

    # ── Admin: available agents list ──────────────────────────────────

    async def list_available_agents(
        self, role: Optional[str] = None, state: Optional[str] = None,
    ) -> List[AvailableAgentDto]:
        """Return APPROVED agents eligible for task assignment, ranked by composite score."""
        from main.app.domain.user.agent.models import SearchAgentApplicationDto
        apps = await self._agent_apps.get_by_criterion(
            SearchAgentApplicationDto(
                status=AgentApplicationStatus.APPROVED.value,
                page=1,
                page_size=200,
            )
        )
        sla_hours = await self._config.get_int("task_sla_hours", fallback=48)
        top_agent_threshold = float(await self._config.get("agent_top_agent_accuracy_threshold") or "4.5")

        result: List[AvailableAgentDto] = []
        for app_data in apps:
            user_id = app_data.get("user_id") if isinstance(app_data, dict) else getattr(app_data, "user_id", None)
            types = app_data.get("types") if isinstance(app_data, dict) else getattr(app_data, "types", [])
            coverage_states = (
                app_data.get("coverage_states") if isinstance(app_data, dict)
                else getattr(app_data, "coverage_states", [])
            )
            availability_status = (
                app_data.get("availability_status") if isinstance(app_data, dict)
                else getattr(app_data, "availability_status", AvailabilityStatus.AVAILABLE.value)
            )
            if not user_id:
                continue
            if role and role not in (types or []):
                continue
            if state and state.upper() not in [s.upper() for s in (coverage_states or [])]:
                continue
            # Exclude unavailable agents from assignment list
            if availability_status == AvailabilityStatus.UNAVAILABLE.value:
                continue

            user = await self._users.get_model(user_id)
            if user is None:
                continue
            active_count = await self._tasks.count_active_for_agent(user_id)
            metrics = await self._quality_scores.compute_metrics(user_id, sla_hours)

            is_top_agent = (
                metrics.accuracy_score >= top_agent_threshold
                and metrics.completion_rate >= 80.0
            )
            # Composite score: accuracy 40%, completion 40%, timeliness 20%
            composite = (
                0.4 * (metrics.accuracy_score / 5.0)
                + 0.4 * (metrics.completion_rate / 100.0)
                + 0.2 * (metrics.timeliness_score / 100.0)
            )
            result.append(
                AvailableAgentDto(
                    agent_id=str(user.id),
                    user_id=str(user.id),
                    first_name=user.first_name,
                    last_name=user.last_name,
                    types=list(types or []),
                    coverage_states=list(coverage_states or []),
                    active_task_count=active_count,
                    rating=round(metrics.accuracy_score, 2) if metrics.accuracy_score else None,
                    is_trusted=user.trust_status == TrustStatus.TRUSTED.value,
                    is_top_agent=is_top_agent,
                    composite_score=round(composite, 4),
                )
            )
        # Rank: Top Agents first, then trusted, then composite score DESC
        result.sort(key=lambda a: (not a.is_top_agent, not a.is_trusted, -a.composite_score))
        return result

    # ── Verification state derivation ─────────────────────────────────

    async def _derive_and_update_verification_status(
        self, verification_id: str,
    ) -> None:
        """Compute verification status from the current state of all its tasks."""
        tasks = await self._tasks.list_for_verification(verification_id)
        if not tasks:
            return

        statuses = {t.status for t in tasks}
        terminal_ok = {TaskStatus.SUBMITTED.value, TaskStatus.APPROVED.value}
        all_approved = all(t.status == TaskStatus.APPROVED.value for t in tasks)
        all_settled = all(t.status in terminal_ok for t in tasks)
        any_submitted = any(t.status == TaskStatus.SUBMITTED.value for t in tasks)
        any_active = any(
            t.status in {TaskStatus.ACCEPTED.value, TaskStatus.IN_PROGRESS.value}
            for t in tasks
        )
        all_pending = statuses == {TaskStatus.PENDING.value}

        if all_approved:
            # All tasks approved → hand off to admin for report review/release (S28-S31).
            # COMPLETED is set exclusively by ReleaseService.release() (S31), not here.
            new_status = VerificationStatus.UNDER_REVIEW
        elif all_settled and any_submitted:
            new_status = VerificationStatus.UNDER_REVIEW
        elif any_active:
            new_status = VerificationStatus.IN_PROGRESS
        elif all_pending:
            return  # no change — stays PAID
        else:
            return

        verification = await self._verifications.get_model(verification_id)
        if verification and verification.status != new_status.value:
            await self._verifications.update(
                verification_id,
                UpdateVerificationDto(status=new_status),
            )
            # When transitioning to UNDER_REVIEW, run conflict detection (S29)
            if new_status == VerificationStatus.UNDER_REVIEW:
                await self._run_conflict_detection(verification_id)

    async def _run_conflict_detection(self, verification_id: str) -> None:
        try:
            from main.app.domain.verification.conflict.service import ConflictService
            svc: ConflictService = di[ConflictService]
            await svc.detect_and_store(verification_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Conflict detection failed for {verification_id}: {exc}")

    # ── Trust elevation ───────────────────────────────────────────────

    async def _maybe_elevate_trust(self, agent_id: str) -> None:
        """Elevate agent to TRUSTED on their first ever submitted task."""
        user = await self._users.get_model(agent_id)
        if user and user.trust_status != TrustStatus.TRUSTED.value:
            await self._users.update(
                agent_id,
                UpdateUserDto(trust_status=TrustStatus.TRUSTED.value),
            )

    # ── Availability auto-management (Phase 16 — S50) ────────────────

    async def _maybe_flip_unavailable(self, agent_id: str) -> None:
        """Auto-set agent UNAVAILABLE when they hit the max active task cap."""
        max_tasks = await self._config.get_int("agent_max_active_tasks", fallback=5)
        active_count = await self._tasks.count_active_for_agent(agent_id)
        if active_count >= max_tasks:
            app = await self._agent_apps.get_by_user_id(agent_id)
            if app and app.availability_status != AvailabilityStatus.UNAVAILABLE.value:
                await self._agent_apps.update(str(app.id), UpdateAgentApplicationDto(
                    availability_status=AvailabilityStatus.UNAVAILABLE.value,
                ))

    async def _maybe_restore_availability(self, agent_id: str) -> None:
        """Restore agent to AVAILABLE when task count drops below cap."""
        max_tasks = await self._config.get_int("agent_max_active_tasks", fallback=5)
        active_count = await self._tasks.count_active_for_agent(agent_id)
        if active_count < max_tasks:
            app = await self._agent_apps.get_by_user_id(agent_id)
            # Only restore if the status was auto-flipped (UNAVAILABLE); leave
            # LIMITED or manually set UNAVAILABLE alone.
            if app and app.availability_status == AvailabilityStatus.UNAVAILABLE.value:
                await self._agent_apps.update(str(app.id), UpdateAgentApplicationDto(
                    availability_status=AvailabilityStatus.AVAILABLE.value,
                ))

    # ── Submit payload validators ─────────────────────────────────────

    async def _validate_submit_payload(
        self, role: TaskRole, payload: Dict[str, Any], task: Task,
    ) -> None:
        if role == TaskRole.FIELD:
            await self._validate_field(payload, task)
        elif role == TaskRole.SURVEYOR:
            self._validate_surveyor(payload)
        elif role == TaskRole.REGISTRY:
            self._validate_registry(payload)
        elif role == TaskRole.LAWYER:
            await self._validate_lawyer(payload, task)

    async def _validate_field(self, p: Dict[str, Any], task: Task) -> None:
        if not p.get("access_confirmed"):
            raise ValidationException(message="access_confirmed is required")
        if not p.get("declaration_signed"):
            raise ValidationException(message="declaration_signed is required")
        from main.app.domain.verification.task.evidence.service import PHOTO_MIN_COUNT
        gps_count = await self._evidence.count_gps_for_task(str(task.id))
        if gps_count < PHOTO_MIN_COUNT:
            raise ValidationException(
                message=f"At least {PHOTO_MIN_COUNT} GPS-stamped photos are required (uploaded: {gps_count})"
            )

    @staticmethod
    def _validate_surveyor(p: Dict[str, Any]) -> None:
        if not p.get("survey_confirmed"):
            raise ValidationException(message="survey_confirmed is required")
        if not p.get("boundary_coords"):
            raise ValidationException(message="boundary_coords (lat/lng) are required")
        if not p.get("declaration_signed"):
            raise ValidationException(message="declaration_signed is required")

    @staticmethod
    def _validate_registry(p: Dict[str, Any]) -> None:
        if not p.get("registry_search_ref"):
            raise ValidationException(message="registry_search_ref is required")
        if not p.get("title_doc_assessment"):
            raise ValidationException(message="title_doc_assessment is required")
        if not p.get("ownership_chain"):
            raise ValidationException(message="ownership_chain is required")
        if not p.get("declaration_signed"):
            raise ValidationException(message="declaration_signed is required")

    async def _validate_lawyer(
        self, p: Dict[str, Any], task: Task,
    ) -> None:
        legal_opinion = p.get("legal_opinion", "")
        if len(str(legal_opinion)) < 200:
            raise ValidationException(
                message="legal_opinion must be at least 200 characters"
            )
        if not p.get("nba_confirmed"):
            raise ValidationException(message="nba_confirmed is required")
        if not p.get("recommendation"):
            raise ValidationException(message="recommendation is required")
        if not p.get("declaration_signed"):
            raise ValidationException(message="declaration_signed is required")
        # Dependency gate: all non-lawyer siblings must be SUBMITTED or APPROVED
        siblings = await self._tasks.list_for_verification(task.verification_id)
        settled = {TaskStatus.SUBMITTED.value, TaskStatus.APPROVED.value}
        for sibling in siblings:
            if sibling.role != TaskRole.LAWYER.value and str(sibling.id) != str(task.id):
                if sibling.status not in settled:
                    raise ValidationException(
                        message="All other agents must submit before the lawyer can submit"
                    )

    # ── Mappers ───────────────────────────────────────────────────────

    @staticmethod
    def _task_to_dto(task: Task) -> TaskDto:
        draft = None
        if task.draft_payload:
            try:
                draft = json.loads(task.draft_payload)
            except (json.JSONDecodeError, ValueError):
                pass
        return TaskDto(
            id=str(task.id),
            verification_id=task.verification_id,
            role=TaskRole(task.role),
            agent_id=task.agent_id,
            status=TaskStatus(task.status),
            pool_released_at=task.pool_released_at,
            accepted_at=task.accepted_at,
            submitted_at=task.submitted_at,
            trust_score=task.trust_score,
            draft_payload=draft,
            date_created=task.date_created,
            date_updated=task.date_updated,
        )

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_task_or_raise(self, task_id: str) -> Task:
        task = await self._tasks.get_task(task_id)
        if task is None:
            raise ResourceNotFoundException(resource="Task")
        return task
