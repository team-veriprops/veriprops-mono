"""Agent onboarding controller (PRD §3.1–3.2).

Frontend service: `frontend/src/components/agents/onboarding/*` (agent-service).
URL shape: `/users/agents/...` (mounted under the user router).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from libre_fastapi_jwt import AuthJWT
from kink import di

from main.app.domain.user.agent.application_draft.controller import agent_application_draft_router
from main.app.domain.user.agent.models import (
    AgentApplicationDetailDto,
    AgentApplicationStatusDto,
    AgentApplicationSummaryDto,
    ApproveAgentApplicationDto,
    RejectAgentApplicationDto,
    SubmitAgentApplicationDto,
)
from main.app.domain.user.agent.service import AgentService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils import RouterUtils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse

agent_router = APIRouter(prefix="/agents", tags=["Agents"])
agent_service: AgentService = di[AgentService]

# Child domain: resumable wizard draft owns its own router (/agents/application/draft).
RouterUtils.add_routers(agent_router, [agent_application_draft_router])


# ── Applicant: submit + status ────────────────────────────────────

@agent_router.post("/application", response_model=SuccessResponse[AgentApplicationStatusDto])
async def submit_application(req: SubmitAgentApplicationDto, request: Request, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    status = await agent_service.submit_application(
        user_id, req, ip_address=ClientUtils.get_client_ip(request)
    )
    return SuccessResponse[AgentApplicationStatusDto](data=status)


@agent_router.get("/application", response_model=SuccessResponse[Optional[AgentApplicationStatusDto]])
async def my_application_status(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    status = await agent_service.get_my_status(user_id)
    return SuccessResponse[Optional[AgentApplicationStatusDto]](data=status)


# ── Admin: approval queue (RBAC: APPROVE_AGENT) ───────────────────

@agent_router.get("/applications", response_model=SuccessResponse[Page[AgentApplicationSummaryDto]])
async def list_applications(
    status: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    result = await agent_service.list_applications(
        status=status, page=page, page_size=page_size, query=query,
    )
    return SuccessResponse[Page[AgentApplicationSummaryDto]](data=result)


@agent_router.get("/applications/{profile_id}", response_model=SuccessResponse[AgentApplicationDetailDto])
async def get_application(
    profile_id: str,
    _admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    detail = await agent_service.get_application_detail(profile_id)
    return SuccessResponse[AgentApplicationDetailDto](data=detail)


@agent_router.post("/applications/{profile_id}/approve", response_model=SuccessResponse[AgentApplicationDetailDto])
async def approve_application(
    profile_id: str,
    req: ApproveAgentApplicationDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    detail = await agent_service.approve_application(profile_id, req, admin_id)
    return SuccessResponse[AgentApplicationDetailDto](data=detail)


@agent_router.post("/applications/{profile_id}/reject", response_model=SuccessResponse[AgentApplicationDetailDto])
async def reject_application(
    profile_id: str,
    req: RejectAgentApplicationDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    detail = await agent_service.reject_application(profile_id, req, admin_id)
    return SuccessResponse[AgentApplicationDetailDto](data=detail)
