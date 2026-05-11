"""Task HTTP routes — admin assignment + agent task execution.

Admin routes:  /api/admin/verifications/{vid}/tasks/...
               /api/admin/tasks/...
               /api/admin/agents/available
Agent routes:  /api/agents/tasks/...
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.task.models import (
    AdminAssignDto,
    AdminReassignDto,
    AvailableAgentDto,
    TaskDto,
)
from main.app.domain.verification.escalation.models import EscalationDto, ReportEscalationDto
from main.app.domain.verification.escalation.service import EscalationService
from main.app.domain.verification.task.evidence.models import EvidenceItemDto, EvidenceType
from main.app.domain.verification.task.evidence.service import EvidenceService
from main.app.domain.verification.task.service import TaskService
from main.appodus_utils.db.models import SuccessResponse

task_service: TaskService = di[TaskService]
evidence_service: EvidenceService = di[EvidenceService]
escalation_service: EscalationService = di[EscalationService]

# ── Admin routers ─────────────────────────────────────────────────────

admin_task_router = APIRouter(prefix="/admin", tags=["Admin - Tasks"])
agent_task_router = APIRouter(prefix="/agents", tags=["Agent - Tasks"])

# ── Admin: tasks scoped to a verification ─────────────────────────────


@admin_task_router.get(
    "/verifications/{vid}/tasks",
    response_model=SuccessResponse[List[TaskDto]],
)
async def list_tasks_for_verification(
    vid: str,
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    tasks = await task_service.list_for_verification(vid)
    return SuccessResponse[List[TaskDto]](data=tasks)


@admin_task_router.post(
    "/verifications/{vid}/tasks/{role}/assign",
    response_model=SuccessResponse[TaskDto],
)
async def admin_assign_task(
    vid: str,
    role: str,
    req: AdminAssignDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Admin directly assigns a specific role-task to an agent (bypasses pool)."""
    tasks = await task_service.list_for_verification(vid)
    matching = [t for t in tasks if t.role.value.upper() == role.upper()]
    if not matching:
        from main.appodus_utils.exception.exceptions import ResourceNotFoundException
        raise ResourceNotFoundException(resource=f"Task with role {role}")
    task = matching[0]
    dto = await task_service.admin_assign(task.id, req.agent_id, admin_id)
    return SuccessResponse[TaskDto](data=dto)


# ── Admin: task-level operations ──────────────────────────────────────


@admin_task_router.post(
    "/tasks/{task_id}/reassign",
    response_model=SuccessResponse[TaskDto],
)
async def admin_reassign_task(
    task_id: str,
    req: AdminReassignDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await task_service.admin_reassign(task_id, req.agent_id, admin_id, req.note)
    return SuccessResponse[TaskDto](data=dto)


@admin_task_router.get(
    "/agents/available",
    response_model=SuccessResponse[List[AvailableAgentDto]],
)
async def list_available_agents(
    role: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Return approved agents eligible for assignment, ranked by trust + load."""
    agents = await task_service.list_available_agents(role=role, state=state)
    return SuccessResponse[List[AvailableAgentDto]](data=agents)


# ── Agent routes ──────────────────────────────────────────────────────


@agent_task_router.get(
    "/tasks/available",
    response_model=SuccessResponse[List[TaskDto]],
)
async def get_available_tasks(
    role: str = Query(..., description="Agent role: FIELD, SURVEYOR, REGISTRY, LAWYER"),
    state: Optional[str] = Query(None),
    authorize: AuthJWT = Depends(),
):
    """PENDING tasks visible to this agent (geo + role filtered)."""
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    tasks = await task_service.list_available_for_agent(agent_id=agent_id, role=role, state=state)
    return SuccessResponse[List[TaskDto]](data=tasks)


@agent_task_router.get(
    "/tasks/active",
    response_model=SuccessResponse[List[TaskDto]],
)
async def get_active_tasks(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    tasks = await task_service.list_active_for_agent(agent_id)
    return SuccessResponse[List[TaskDto]](data=tasks)


@agent_task_router.get(
    "/tasks/completed",
    response_model=SuccessResponse[List[TaskDto]],
)
async def get_completed_tasks(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    tasks = await task_service.list_completed_for_agent(agent_id)
    return SuccessResponse[List[TaskDto]](data=tasks)


@agent_task_router.get(
    "/tasks/{task_id}",
    response_model=SuccessResponse[TaskDto],
)
async def get_task(task_id: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    dto = await task_service.get_task(task_id)
    return SuccessResponse[TaskDto](data=dto)


@agent_task_router.post(
    "/tasks/{task_id}/accept",
    response_model=SuccessResponse[TaskDto],
)
async def accept_task(task_id: str, authorize: AuthJWT = Depends()):
    """First-come-first-served accept.  409 if another agent already took it."""
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    dto = await task_service.agent_accept(task_id, agent_id)
    return SuccessResponse[TaskDto](data=dto)


@agent_task_router.post(
    "/tasks/{task_id}/decline",
    response_model=SuccessResponse[TaskDto],
)
async def decline_task(task_id: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    dto = await task_service.agent_decline(task_id, agent_id)
    return SuccessResponse[TaskDto](data=dto)


@agent_task_router.put(
    "/tasks/{task_id}/draft",
    response_model=SuccessResponse[TaskDto],
)
async def save_draft(task_id: str, payload: dict, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    dto = await task_service.save_draft(task_id, agent_id, payload)
    return SuccessResponse[TaskDto](data=dto)


@agent_task_router.post(
    "/tasks/{task_id}/evidence",
    response_model=SuccessResponse[EvidenceItemDto],
)
async def upload_evidence(
    task_id: str,
    file: UploadFile,
    evidence_type: EvidenceType = Form(EvidenceType.PHOTO),
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None),
    captured_at: Optional[str] = Form(None),
    authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    file_bytes = await file.read()
    captured_dt = None
    if captured_at:
        from datetime import datetime
        try:
            captured_dt = datetime.fromisoformat(captured_at)
        except ValueError:
            pass
    dto = await evidence_service.upload(
        task_id=task_id,
        uploader_id=agent_id,
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        evidence_type=evidence_type,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        captured_at=captured_dt,
    )
    return SuccessResponse[EvidenceItemDto](data=dto)


@agent_task_router.post(
    "/tasks/{task_id}/submit",
    response_model=SuccessResponse[TaskDto],
)
async def submit_task(task_id: str, payload: dict, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    dto = await task_service.submit(task_id, agent_id, payload)
    return SuccessResponse[TaskDto](data=dto)


@agent_task_router.post(
    "/tasks/{task_id}/escalation",
    response_model=SuccessResponse[EscalationDto],
)
async def report_escalation(
    task_id: str, req: ReportEscalationDto, authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    agent_id = authorize.get_jwt_subject()
    dto = await escalation_service.report(task_id, agent_id, req)
    return SuccessResponse[EscalationDto](data=dto)


# Export the combined router used by task/__init__.py for import checking;
# actual mounting happens in domain/__init__.py via admin_task_router + agent_task_router.
task_router = APIRouter()
task_router.include_router(admin_task_router)
task_router.include_router(agent_task_router)
