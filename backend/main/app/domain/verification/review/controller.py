"""Admin review & report-release controller (PRD §8).

URL shape: /admin/review/... — RBAC-gated (MANAGE_VERIFICATIONS). Frontend service:
frontend/src/components/admin/verifications/libs/review-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.report.models import ReportDto
from main.app.domain.verification.review.models import (
    ApproveTaskDto,
    FailVerificationDto,
    RejectTaskDto,
    ReleaseDto,
    ReviewConflictDto,
    ReviewStateDto,
)
from main.app.domain.verification.review.service import ReviewContext, ReviewService
from main.app.domain.verification.task.models import TaskAssignmentMode, TaskDto, TaskState
from main.appodus_utils.db.models import SuccessResponse

review_router = APIRouter(prefix="/admin/review", tags=["Admin: Review & Release"])
review_service: ReviewService = di[ReviewService]


def _task_dto(t) -> TaskDto:
    return TaskDto(
        id=t.id, verification_id=t.verification_id, role=AgentRole(t.role),
        tier=VerificationTier(t.tier), state=TaskState(t.state),
        assigned_agent_id=t.assigned_agent_id,
        assignment_mode=TaskAssignmentMode(t.assignment_mode) if t.assignment_mode else None,
        in_pool=bool(t.in_pool), decline_count=t.decline_count or 0,
        submitted_at=t.submitted_at, approved_at=t.approved_at,
    )


def _report_dto(r) -> ReportDto:
    from main.app.core.state.status import ReportState
    return ReportDto(
        id=r.id, verification_id=r.verification_id, report_version=r.report_version,
        state=ReportState(r.state), composite_trust_score=r.composite_trust_score,
        findings=r.findings, release_reason=r.release_reason, released_at=r.released_at,
        superseded_at=r.superseded_at, date_created=r.date_created,
    )


def _state_dto(verification_id: str, ctx: ReviewContext) -> ReviewStateDto:
    return ReviewStateDto(
        verification_id=verification_id,
        status=VerificationStatus(ctx.verification.status),
        tier=ctx.tier,
        tasks=[_task_dto(t) for t in ctx.tasks],
        conflicts=[ReviewConflictDto(**c.as_dict()) for c in ctx.conflicts],
        projected_trust_score=ctx.projected_trust_score,
        all_approved=ctx.all_approved,
        releasable=ctx.releasable,
        report=_report_dto(ctx.report) if ctx.report else None,
        findings={role.value: payload for role, payload in ctx.submissions.items()},
    )


@review_router.get("/{verification_id}", response_model=SuccessResponse[ReviewStateDto])
async def get_review(
    verification_id: str,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))


@review_router.post("/{verification_id}/tasks/{role}/approve", response_model=SuccessResponse[ReviewStateDto])
async def approve_task(
    verification_id: str, role: AgentRole, req: ApproveTaskDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    await review_service.approve_task(verification_id, role, req.quality, admin_id)
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))


@review_router.post("/{verification_id}/tasks/{role}/reject", response_model=SuccessResponse[ReviewStateDto])
async def reject_task(
    verification_id: str, role: AgentRole, req: RejectTaskDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    await review_service.reject_task(verification_id, role, req.reason, admin_id)
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))


@review_router.post("/{verification_id}/tasks/{role}/reopen", response_model=SuccessResponse[ReviewStateDto])
async def reopen_task(
    verification_id: str, role: AgentRole,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    await review_service.reopen_task(verification_id, role, admin_id)
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))


@review_router.post("/{verification_id}/release", response_model=SuccessResponse[ReviewStateDto])
async def release(
    verification_id: str, req: ReleaseDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    await review_service.release(verification_id, admin_id, req.reason)
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))


@review_router.post("/{verification_id}/fail", response_model=SuccessResponse[ReviewStateDto])
async def fail(
    verification_id: str, req: FailVerificationDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    await review_service.fail(verification_id, req.reason, admin_id)
    ctx = await review_service.get_review_context(verification_id)
    return SuccessResponse[ReviewStateDto](data=_state_dto(verification_id, ctx))
