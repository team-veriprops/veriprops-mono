"""Agent task-execution controller (PRD §7.1, §7.3).

URL shape: /agents/tasks/... — the agent's own work surface. Identity is the JWT
subject; authorization is ownership-based (a task belongs to the accepting/assigned
agent), enforced in the service. Admin assignment lives on the admin verification
router (§6.3). Frontend service: frontend/src/components/agents/libs/agent-task-service.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.audit.models import AuditActivityPageDto
from main.app.domain.verification.task.evidence.models import EvidenceDto, EvidenceItem, EvidenceKind
from main.app.domain.verification.task.evidence.service import EvidenceService
from main.app.domain.verification.task.models import (
    AgentDashboardDto,
    AgentTaskDto,
    DeclineTaskDto,
    SubmitTaskDto,
    TaskAssignmentMode,
    TaskState,
    VerificationTask,
)
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta, SuccessResponse

agent_task_router = APIRouter(prefix="/agents/tasks", tags=["Agent: Tasks"])
task_service: VerificationTaskService = di[VerificationTaskService]
evidence_service: EvidenceService = di[EvidenceService]


async def _to_agent_dto(t: VerificationTask) -> AgentTaskDto:
    # t.id is a uuid.UUID on the ORM row; the evidence reference column is hex text.
    evidence_count = await evidence_service.count_for_task(Utils.uuid_to_hex(t.id))
    return AgentTaskDto(
        id=t.id, verification_id=t.verification_id, role=AgentRole(t.role),
        tier=VerificationTier(t.tier), state=TaskState(t.state), in_pool=bool(t.in_pool),
        assignment_mode=TaskAssignmentMode(t.assignment_mode) if t.assignment_mode else None,
        accept_deadline_at=t.accept_deadline_at, remote_bonus_minor=t.remote_bonus_minor,
        submission_payload=t.submission_payload, rejection_reason=t.rejection_reason,
        evidence_count=evidence_count, assigned_at=t.assigned_at,
        accepted_at=t.accepted_at, submitted_at=t.submitted_at,
    )


def _evidence_dto(e: EvidenceItem) -> EvidenceDto:
    return EvidenceDto(
        id=e.id, task_id=e.task_id, verification_id=e.verification_id, kind=EvidenceKind(e.kind),
        storage_url=e.storage_url, mime_type=e.mime_type, size_bytes=e.size_bytes,
        content_sha256=e.content_sha256, gps_latitude=e.gps_latitude,
        gps_longitude=e.gps_longitude, captured_at=e.captured_at, uploaded_at=e.uploaded_at,
    )


@agent_task_router.get("", response_model=SuccessResponse[Page[AgentTaskDto]])
async def list_my_tasks(
    state: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    states = [state] if state else None
    rows, total = await task_service.list_for_agent(agent_id, states, page, page_size)
    items = [await _to_agent_dto(t) for t in rows]
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return SuccessResponse[Page[AgentTaskDto]](data=Page[AgentTaskDto](
        items=items,
        meta=PaginationMeta(
            page=page, page_size=page_size, count=len(items), total=total,
            total_pages=total_pages,
            prev_page=page - 1 if page > 0 else None,
            next_page=page + 1 if (page + 1) < total_pages else None,
        ),
    ))


@agent_task_router.get("/summary", response_model=SuccessResponse[AgentDashboardDto])
async def get_dashboard_summary(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[AgentDashboardDto](data=await task_service.agent_summary(agent_id))


@agent_task_router.post("/{task_id}/accept", response_model=SuccessResponse[AgentTaskDto])
async def accept_task(task_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    task = await task_service.accept(task_id, agent_id)
    return SuccessResponse[AgentTaskDto](data=await _to_agent_dto(task))


@agent_task_router.post("/{task_id}/decline", response_model=SuccessResponse[AgentTaskDto])
async def decline_task(task_id: str, req: DeclineTaskDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    task = await task_service.decline(task_id, agent_id, req.reason)
    return SuccessResponse[AgentTaskDto](data=await _to_agent_dto(task))


@agent_task_router.post("/{task_id}/start", response_model=SuccessResponse[AgentTaskDto])
async def start_task(task_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    task = await task_service.start(task_id, agent_id)
    return SuccessResponse[AgentTaskDto](data=await _to_agent_dto(task))


@agent_task_router.post("/{task_id}/evidence", response_model=SuccessResponse[EvidenceDto])
async def add_evidence(
    task_id: str,
    file: UploadFile = File(...),
    kind: EvidenceKind = Form(default=EvidenceKind.PHOTO),
    gps_latitude: Optional[float] = Form(default=None),
    gps_longitude: Optional[float] = Form(default=None),
    authorize: AuthJWT = Depends(),
):
    """Upload a piece of proof-of-work (§4.5, §7.3a). Content hash + server GPS/timestamp
    are stamped at receipt; the client GPS is a hint only."""
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    file_bytes = await file.read()
    item = await task_service.add_evidence(
        task_id, agent_id, file_bytes=file_bytes, kind=kind,
        mime_type=file.content_type, gps_latitude=gps_latitude, gps_longitude=gps_longitude,
    )
    return SuccessResponse[EvidenceDto](data=_evidence_dto(item))


@agent_task_router.get("/{task_id}/evidence", response_model=SuccessResponse[List[EvidenceDto]])
async def list_evidence(task_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    items = await evidence_service.list_for_task(task_id)
    return SuccessResponse[List[EvidenceDto]](data=[_evidence_dto(e) for e in items])


@agent_task_router.post("/{task_id}/submit", response_model=SuccessResponse[AgentTaskDto])
async def submit_task(task_id: str, req: SubmitTaskDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    task = await task_service.submit(task_id, agent_id, req.payload)
    return SuccessResponse[AgentTaskDto](data=await _to_agent_dto(task))


@agent_task_router.get(
    "/{task_id}/history", response_model=SuccessResponse[AuditActivityPageDto]
)
async def get_task_history(
    task_id: str,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    """PII-safe state-transition history for one of the agent's own tasks (§19.3 / R19.3)."""
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    result = await task_service.task_history(task_id, agent_id, page, page_size)
    return SuccessResponse[AuditActivityPageDto](data=result)
