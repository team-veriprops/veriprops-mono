"""Customer tracking & evidence service (PRD §9).

Read-only projection of the verification aggregate into the customer's live tracking
snapshot and evidence feed. Ownership is enforced by delegating to
``VerificationService.get_owned`` (the single ownership gate); every customer-facing
projection strips agent identity to the four safe fields and withholds interim signal
until admin review-approval (§9.3).
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.core.sla import (
    ACTIVE_SLA_STATES,
    SLA_BUSINESS_DAYS,
    business_days_between,
    compute_sla_health,
)
from main.app.core.state.dependencies import blocking_roles, required_task_count, roles_for_tier
from main.app.core.state.status import AgentRole, TaskState, VerificationTier, VerificationStatus
from main.app.domain.audit.models import AuditActivityPageDto
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.agent.profile.repo import AgentProfileRepo
from main.app.domain.user.repo import UserRepo
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.evidence.service import EvidenceService
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.app.domain.verification.tracking.labels import (
    LAWYER_AWAITING_LABEL,
    customer_sla_label,
    customer_status_label,
    customer_task_state,
    interim_message,
)
from main.app.domain.verification.tracking.models import (
    AssignedAgentDto,
    CustomerDashboardDto,
    CustomerEvidenceDto,
    InterimMilestoneDto,
    ResumableDraftDto,
    SlaTrackerDto,
    TrackingTaskDto,
    VerificationListItemDto,
    VerificationTrackingDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# review_decision string recorded by the review service on approval (§8.3). A task is
# customer-visible as an interim milestone / its evidence surfaces once this is set,
# which stays true through release (state→APPROVED) and clears on reopen.
_REVIEW_APPROVED = "APPROVED"
# Task states counted as "work done" for the customer progress bar — reaches 100% at
# UNDER_REVIEW (every required task SUBMITTED), matching §9.3.
_SETTLED_STATES = {TaskState.SUBMITTED.value, TaskState.APPROVED.value}
_EVIDENCE_PREVIEW_LIMIT = 3
# Number of most-recent verifications surfaced on the portal dashboard.
_DASHBOARD_RECENT_LIMIT = 5
# Portal dashboard rollups (§9). "In progress" reuses the SLA-active set so the number
# always matches the SLA countdown surface.
_AWAITING_PAYMENT_STATUSES = {
    VerificationStatus.SUBMITTED.value,
    VerificationStatus.PAYMENT_PENDING.value,
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CustomerTrackingService:
    def __init__(
        self,
        verification_service: VerificationService,
        verification_repo: VerificationRepo,
        task_repo: VerificationTaskRepo,
        evidence_service: EvidenceService,
        user_repo: UserRepo,
        agent_profile_repo: AgentProfileRepo,
        property_repo: PropertyRepo,
        audit_service: AuditLogService,
    ):
        self._verifications = verification_service
        self._verification_repo = verification_repo
        self._tasks = task_repo
        self._evidence = evidence_service
        self._users = user_repo
        self._agent_profiles = agent_profile_repo
        self._properties = property_repo
        self._audit = audit_service

    # ── My Verifications list (§9) ──────────────────────────────────────────

    async def list_my_verifications(
        self, customer_id: str, page: int, page_size: int
    ) -> Page[VerificationListItemDto]:
        rows, total = await self._verification_repo.page_for_customer(
            customer_id, offset=page * page_size, limit=page_size,
        )
        items = [await self._list_item(v) for v in rows]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[VerificationListItemDto](
            items=items,
            meta=PaginationMeta(
                page=page, page_size=page_size, count=len(items), total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    async def summary(self, customer_id: str) -> CustomerDashboardDto:
        """Portal home rollups (§9): counts by status + the most recent verifications.
        Every number is derived server-side; the client only renders."""
        raw = await self._verification_repo.count_by_status_for_customer(customer_id)
        status_counts = {VerificationStatus(s): c for s, c in raw.items()}
        recent_page = await self.list_my_verifications(customer_id, 0, _DASHBOARD_RECENT_LIMIT)
        return CustomerDashboardDto(
            total=sum(status_counts.values()),
            draft=raw.get(VerificationStatus.DRAFT.value, 0),
            awaiting_payment=sum(raw.get(s, 0) for s in _AWAITING_PAYMENT_STATUSES),
            in_progress=sum(raw.get(s, 0) for s in ACTIVE_SLA_STATES),
            completed=raw.get(VerificationStatus.COMPLETED.value, 0),
            status_counts=status_counts,
            recent=recent_page.items,
            resumable_draft=await self._resumable_draft(customer_id),
        )

    async def _resumable_draft(self, customer_id: str):
        """The most recent unpaid verification the customer can resume (§17.1 recovery)."""
        v = await self._verification_repo.latest_unpaid_for_customer(customer_id)
        if v is None:
            return None
        return ResumableDraftDto(
            id=v.id, vid=v.vid, status=VerificationStatus(v.status),
            tier=VerificationTier(v.tier) if v.tier else None,
            draft_step=v.draft_step or 0,
            # SUBMITTED / PAYMENT_PENDING resume at pay; a DRAFT resumes in the wizard.
            needs_payment=v.status in _AWAITING_PAYMENT_STATUSES,
        )

    async def _list_item(self, v) -> VerificationListItemDto:
        address = None
        if v.property_id:
            prop = await self._properties.get_model(v.property_id)
            address = prop.address if prop else None
        return VerificationListItemDto(
            id=v.id, vid=v.vid,
            tier=VerificationTier(v.tier) if v.tier else None,
            status=VerificationStatus(v.status),
            status_label=customer_status_label(v.status),
            address=address, sla_due_date=v.sla_due_date, date_created=v.date_created,
        )

    # ── Tracking snapshot (§9.1) — the shared poll + SSE-initial-frame body ──

    async def get_snapshot(self, verification_id: str, customer_id: str) -> VerificationTrackingDto:
        v = await self._verifications.get_owned(verification_id, customer_id)
        tier = VerificationTier(v.tier) if v.tier else None
        tasks = await self._tasks.list_for_verification(verification_id)
        by_role = {AgentRole(t.role): t for t in tasks}

        address = None
        if v.property_id:
            prop = await self._properties.get_model(v.property_id)
            address = prop.address if prop else None

        return VerificationTrackingDto(
            id=v.id,
            vid=v.vid,
            tier=tier,
            status=VerificationStatus(v.status),
            status_label=customer_status_label(v.status),
            address=address,
            paused=bool(v.paused),
            paid_at=v.paid_at,
            sla=self._sla_tracker(v, tier),
            progress_percent=self._progress_percent(tier, tasks),
            required_task_count=required_task_count(tier) if tier else 0,
            approved_task_count=sum(1 for t in tasks if t.state == TaskState.APPROVED.value),
            tasks=self._tracking_tasks(tier, by_role),
            agents=await self._assigned_agents(tasks),
            interim_milestones=self._interim_milestones(tasks),
            evidence_preview=await self._evidence_preview(tasks),
        )

    # ── Evidence feed (§9.4) — review-approved tasks only (D17) ──────────────

    async def list_evidence(
        self, verification_id: str, customer_id: str, page: int, page_size: int
    ) -> Page[CustomerEvidenceDto]:
        await self._verifications.get_owned(verification_id, customer_id)
        tasks = await self._tasks.list_for_verification(verification_id)
        visible = self._visible_task_roles(tasks)
        items = [e for e in await self._evidence.list_for_verification(verification_id)
                 if e.task_id in visible]
        total = len(items)
        window = items[page * page_size: page * page_size + page_size]
        dtos = [await self._evidence_dto(e, visible[e.task_id]) for e in window]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[CustomerEvidenceDto](
            items=dtos,
            meta=PaginationMeta(
                page=page, page_size=page_size, count=len(dtos), total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    async def activity(
        self, verification_id: str, customer_id: str, page: int, page_size: int
    ) -> AuditActivityPageDto:
        """PII-safe verification timeline for the customer (reuses the audit read model)."""
        await self._verifications.get_owned(verification_id, customer_id)
        return await self._audit.get_activity_log(
            resource_type="verification", resource_id=verification_id,
            page=page, page_size=page_size,
        )

    # ── projections ──────────────────────────────────────────────────────────

    def _sla_tracker(self, v, tier: Optional[VerificationTier]) -> SlaTrackerDto:
        today = Utils.datetime_now().date()
        health, remaining = compute_sla_health(v.status, v.sla_due_date, today)
        total = SLA_BUSINESS_DAYS[tier] if tier else None
        elapsed = None
        if v.paid_at:
            elapsed = min(business_days_between(v.paid_at, today), total) if total else \
                business_days_between(v.paid_at, today)
        return SlaTrackerDto(
            expected_date=v.sla_due_date,
            health=health,
            label=customer_sla_label(health),
            business_days_remaining=remaining,
            elapsed_business_days=elapsed,
            total_business_days=total,
        )

    def _progress_percent(self, tier: Optional[VerificationTier], tasks) -> int:
        required = required_task_count(tier) if tier else 0
        if not required:
            return 0
        settled = sum(1 for t in tasks if t.state in _SETTLED_STATES)
        return int((settled / required) * 100)

    def _tracking_tasks(self, tier: Optional[VerificationTier], by_role) -> List[TrackingTaskDto]:
        if not tier:
            return []
        submitted = [r for r, t in by_role.items() if t.state in _SETTLED_STATES]
        steps: List[TrackingTaskDto] = []
        for role in roles_for_tier(tier):
            task = by_role.get(role)
            if task is None:
                # Not yet instantiated. A dependency-blocked Lawyer shows "Awaiting other
                # stages"; any other not-yet-created role reads as Pending.
                locked = bool(blocking_roles(tier, role, submitted))
                steps.append(TrackingTaskDto(
                    role=role,
                    state_label=LAWYER_AWAITING_LABEL if locked else customer_task_state(TaskState.PENDING),
                    locked=locked,
                ))
                continue
            steps.append(TrackingTaskDto(
                role=role,
                state_label=customer_task_state(task.state),
                completed=task.state == TaskState.APPROVED.value,
                submitted_at=task.submitted_at,
                approved_at=task.approved_at,
            ))
        return steps

    async def _assigned_agents(self, tasks) -> List[AssignedAgentDto]:
        agents: List[AssignedAgentDto] = []
        for t in tasks:
            if not t.assigned_agent_id:
                continue
            user = await self._users.get_model(t.assigned_agent_id)
            if user is None:
                continue
            profile = await self._agent_profiles.get_by_user_id(t.assigned_agent_id)
            approved = set(profile.approved_roles or []) if profile else set()
            agents.append(AssignedAgentDto(
                role=AgentRole(t.role),
                first_name=user.first_name,  # only the safe fields cross the boundary
                avatar_url=user.avatar_url,
                verified=t.role in approved,
            ))
        return agents

    def _interim_milestones(self, tasks) -> List[InterimMilestoneDto]:
        milestones: List[InterimMilestoneDto] = []
        for t in tasks:
            if t.review_decision != _REVIEW_APPROVED:
                continue  # withheld until admin review (§9.3)
            role = AgentRole(t.role)
            milestones.append(InterimMilestoneDto(
                role=role,
                message=interim_message(role),
                note=t.interim_note,
                at=t.approved_at or t.submitted_at,
            ))
        return milestones

    async def _evidence_preview(self, tasks) -> List[CustomerEvidenceDto]:
        visible = self._visible_task_roles(tasks)
        if not visible:
            return []
        items = [e for e in await self._evidence.list_for_verification(tasks[0].verification_id)
                 if e.task_id in visible][:_EVIDENCE_PREVIEW_LIMIT]
        return [await self._evidence_dto(e, visible[e.task_id]) for e in items]

    def _visible_task_roles(self, tasks) -> dict:
        """task_id → role for tasks whose evidence the customer may see (review-approved, D17)."""
        return {t.id: AgentRole(t.role) for t in tasks if t.review_decision == _REVIEW_APPROVED}

    async def _evidence_dto(self, e, role: AgentRole) -> CustomerEvidenceDto:
        return CustomerEvidenceDto(
            id=e.id,
            role=role,
            kind=e.kind,
            url=await self._evidence.presigned_url(e),
            mime_type=e.mime_type,
            content_sha256=e.content_sha256,
            gps_latitude=e.gps_latitude,
            gps_longitude=e.gps_longitude,
            captured_at=e.captured_at,
            uploaded_at=e.uploaded_at,
        )
