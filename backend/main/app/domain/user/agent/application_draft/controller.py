"""Resumable agent-application wizard draft endpoints (PRD §3.1).

Frontend service: `frontend/src/components/agents/onboarding/*` (agent-service).
URL shape: `/users/agents/application/draft` (mounted under the agent router).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.agent.application_draft.models import (
    AgentApplicationDraftDto,
    SaveAgentApplicationDraftDto,
)
from main.app.domain.user.agent.application_draft.service import AgentApplicationDraftService
from main.appodus_utils.db.models import SuccessResponse

agent_application_draft_router = APIRouter(prefix="/application/draft", tags=["Agents"])
draft_service: AgentApplicationDraftService = di[AgentApplicationDraftService]


@agent_application_draft_router.get("", response_model=SuccessResponse[Optional[AgentApplicationDraftDto]])
async def get_application_draft(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    draft = await draft_service.get_draft(user_id)
    return SuccessResponse[Optional[AgentApplicationDraftDto]](data=draft)


@agent_application_draft_router.put("", response_model=SuccessResponse[AgentApplicationDraftDto])
async def save_application_draft(req: SaveAgentApplicationDraftDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    draft = await draft_service.save_draft(user_id, req)
    return SuccessResponse[AgentApplicationDraftDto](data=draft)
