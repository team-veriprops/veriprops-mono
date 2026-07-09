"""Resumable agent-application wizard draft (PRD §3.1).

One active draft per user (mirrors ``auth/signup_draft``): the 4-step wizard's
payload is persisted so the applicant can resume where they left off.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


# ─── ORM ──────────────────────────────────────────────────────────

class AgentApplicationDraft(BaseEntity):
    """Resumable wizard state, one active draft per user (mirrors signup_drafts)."""

    __tablename__ = "agent_application_drafts"

    user_id = Column(String(36), nullable=False, index=True)
    step = Column(Integer, nullable=False, server_default="0")
    payload = Column(Text, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAgentApplicationDraftDto(Object):
    user_id: str
    step: int = 0
    payload: str
    expires_at: datetime


class UpdateAgentApplicationDraftDto(Object):
    step: Optional[int] = None
    payload: Optional[str] = None


class SearchAgentApplicationDraftDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None


class QueryAgentApplicationDraftDto(BaseQueryDto):
    user_id: Optional[str] = None
    step: Optional[int] = None


class AgentApplicationDraftDto(Object):
    """Wizard draft as the frontend consumes it (payload parsed to an object)."""

    step: int
    payload: dict
    date_updated: Optional[datetime] = None


class SaveAgentApplicationDraftDto(Object):
    step: int
    payload: dict
