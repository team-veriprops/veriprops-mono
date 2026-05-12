"""Task review HTTP routes — admin approve/reject/reopen (S28) + quality score (S49).

URL shape: /api/admin/tasks/{task_id}/...
All endpoints require MANAGE_VERIFICATIONS permission.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.user.agent.models import AgentQualityScoreDto, CreateQualityScoreDto
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.task.review.models import (
    ApproveTaskDto,
    RejectTaskDto,
    ReopenTaskDto,
    TaskReviewDto,
)
from main.app.domain.verification.task.review.service import TaskReviewService
from main.app.domain.verification.task.service import TaskService
from main.appodus_utils.db.models import SuccessResponse

review_service: TaskReviewService = di[TaskReviewService]
task_service: TaskService = di[TaskService]

task_review_router = APIRouter(prefix="/admin/tasks", tags=["Admin - Task Review"])


@task_review_router.post(
    "/{task_id}/approve",
    response_model=SuccessResponse[TaskReviewDto],
)
async def approve_task(
    task_id: str,
    req: ApproveTaskDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await review_service.approve(task_id, admin_id, req.note)
    return SuccessResponse[TaskReviewDto](data=dto)


@task_review_router.post(
    "/{task_id}/reject",
    response_model=SuccessResponse[TaskReviewDto],
)
async def reject_task(
    task_id: str,
    req: RejectTaskDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await review_service.reject(task_id, admin_id, req.reason)
    return SuccessResponse[TaskReviewDto](data=dto)


@task_review_router.post(
    "/{task_id}/reopen",
    response_model=SuccessResponse[TaskReviewDto],
)
async def reopen_task(
    task_id: str,
    req: ReopenTaskDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await review_service.reopen(task_id, admin_id, req.reason)
    return SuccessResponse[TaskReviewDto](data=dto)


@task_review_router.post(
    "/{task_id}/quality-score",
    response_model=SuccessResponse[AgentQualityScoreDto],
)
async def assign_quality_score(
    task_id: str,
    req: CreateQualityScoreDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await task_service.assign_quality_score(task_id, req, admin_id)
    return SuccessResponse[AgentQualityScoreDto](data=dto)
