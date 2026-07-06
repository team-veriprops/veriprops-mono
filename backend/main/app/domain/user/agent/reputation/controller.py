"""Agent reputation & coverage controller (PRD §16).

Agent: /agents/me/{metrics,profile,availability,coverage} (JWT). Admin: ranked suggested
agents for a task assignment (RBAC ASSIGN_AGENT). Frontend services:
frontend/src/components/agents/reputation/libs/* + admin assignment picker.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.coverage.models import AgentCoverageInputDto
from main.app.domain.user.agent.profile.models import AvailabilityStatus
from main.app.domain.user.agent.reputation.models import (
    AgentMetricsDto,
    AgentProfileSummaryDto,
    SetAvailabilityDto,
    SuggestedAgentDto,
)
from main.app.domain.user.agent.reputation.service import AgentReputationService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

agent_reputation_router = APIRouter(prefix="/agents/me", tags=["Agent: Reputation & Coverage"])
admin_suggested_agents_router = APIRouter(prefix="/admin/agents", tags=["Admin: Agent Assignment"])
reputation_service: AgentReputationService = di[AgentReputationService]


# ── Agent ─────────────────────────────────────────────────────────

@agent_reputation_router.get("/metrics", response_model=SuccessResponse[AgentMetricsDto])
async def my_metrics(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    return SuccessResponse[AgentMetricsDto](data=await reputation_service.get_metrics(str(authorize.get_jwt_subject())))


@agent_reputation_router.get("/profile", response_model=SuccessResponse[AgentProfileSummaryDto])
async def my_profile(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    return SuccessResponse[AgentProfileSummaryDto](
        data=await reputation_service.get_profile_summary(str(authorize.get_jwt_subject()))
    )


@agent_reputation_router.put("/availability", response_model=SuccessResponse[AvailabilityStatus])
async def set_availability(req: SetAvailabilityDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    effective = await reputation_service.set_availability(str(authorize.get_jwt_subject()), req.availability)
    return SuccessResponse[AvailabilityStatus](data=effective)


@agent_reputation_router.get("/coverage", response_model=SuccessResponse[List[AgentCoverageInputDto]])
async def my_coverage(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    return SuccessResponse[List[AgentCoverageInputDto]](
        data=await reputation_service.list_coverage(str(authorize.get_jwt_subject()))
    )


@agent_reputation_router.put("/coverage", response_model=SuccessResponse[List[AgentCoverageInputDto]])
async def set_coverage(areas: List[AgentCoverageInputDto], authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    return SuccessResponse[List[AgentCoverageInputDto]](
        data=await reputation_service.set_coverage(str(authorize.get_jwt_subject()), areas)
    )


# ── Admin assignment ranking (ASSIGN_AGENT) ───────────────────────

@admin_suggested_agents_router.get(
    "/suggested", response_model=SuccessResponse[List[SuggestedAgentDto]]
)
async def suggested_agents(
    verification_id: str,
    role: AgentRole,
    _admin_id: str = Depends(require_permission(Permission.ASSIGN_AGENT)),
):
    return SuccessResponse[List[SuggestedAgentDto]](
        data=await reputation_service.suggested_agents(verification_id, role)
    )
