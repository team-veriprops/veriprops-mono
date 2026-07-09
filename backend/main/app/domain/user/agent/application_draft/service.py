"""Resumable agent-application wizard draft service (PRD §3.1).

Owns the one-active-draft-per-user lifecycle: load, upsert, and discard (mirrors
``auth/signup_draft``). The parent ``AgentService`` delegates draft discard here
once an application is submitted.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from kink import inject

from main.app.domain.user.agent.application_draft.models import (
    AgentApplicationDraftDto,
    CreateAgentApplicationDraftDto,
    SaveAgentApplicationDraftDto,
    UpdateAgentApplicationDraftDto,
)
from main.app.domain.user.agent.application_draft.repo import AgentApplicationDraftRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

_DRAFT_TTL_DAYS = 30


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AgentApplicationDraftService:
    def __init__(self, draft_repo: AgentApplicationDraftRepo):
        self._draft_repo = draft_repo

    async def get_draft(self, user_id: str) -> Optional[AgentApplicationDraftDto]:
        draft = await self._draft_repo.get_active_for_user(user_id)
        if not draft:
            return None
        return AgentApplicationDraftDto(
            step=draft.step,
            payload=json.loads(draft.payload) if draft.payload else {},
            date_updated=draft.date_updated or draft.date_created,
        )

    async def save_draft(self, user_id: str, dto: SaveAgentApplicationDraftDto) -> AgentApplicationDraftDto:
        payload_json = json.dumps(dto.payload)
        existing = await self._draft_repo.get_active_for_user(user_id)
        if existing:
            await self._draft_repo.update(
                existing.id, UpdateAgentApplicationDraftDto(step=dto.step, payload=payload_json)
            )
        else:
            await self._draft_repo.create(CreateAgentApplicationDraftDto(
                user_id=user_id,
                step=dto.step,
                payload=payload_json,
                expires_at=Utils.datetime_now() + timedelta(days=_DRAFT_TTL_DAYS),
            ))
        return AgentApplicationDraftDto(step=dto.step, payload=dto.payload, date_updated=Utils.datetime_now())

    async def discard(self, user_id: str) -> None:
        existing = await self._draft_repo.get_active_for_user(user_id)
        if existing:
            await self._draft_repo.soft_delete(existing.id)
