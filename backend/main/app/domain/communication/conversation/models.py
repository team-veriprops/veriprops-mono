"""Conversation (thread) domain (PRD §11.1).

One thread per verification per channel — Customer↔Admin and (task-taggable) Admin↔Agent —
plus a per-user General Support thread not tied to a verification. The thread row is thin;
messages accrete in ``chat_message`` and per-user read state in ``conversation_participant``.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ConversationType(str, enum.Enum):
    """Which mediated channel a thread carries (PRD §11.1, §4.6)."""

    CUSTOMER_ADMIN = "CUSTOMER_ADMIN"   # customer ↔ admin, one per verification
    ADMIN_AGENT = "ADMIN_AGENT"         # admin ↔ agent(s), one per verification, task-taggable
    GENERAL_SUPPORT = "GENERAL_SUPPORT"  # account/billing/general, one per user, no verification


# ─── ORM ──────────────────────────────────────────────────────────

class Conversation(BaseEntity):
    __tablename__ = "conversations"

    type = Column(String(20), nullable=False)
    # Null for GENERAL_SUPPORT; set for the two verification-scoped channels.
    verification_id = Column(String(36), nullable=True, index=True)
    subject = Column(String(200), nullable=True)
    # ``created_by`` (the thread opener) is the inherited BaseEntity audit column.
    last_message_at = Column(UTCDateTime, nullable=True)
    closed = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("ix_conversations_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateConversationDto(Object):
    type: ConversationType
    verification_id: Optional[str] = None
    subject: Optional[str] = None
    created_by: str
    last_message_at: Optional[datetime] = None


class UpdateConversationDto(Object):
    subject: Optional[str] = None
    closed: Optional[bool] = None


class QueryConversationDto(BaseQueryDto):
    type: Optional[str] = None
    verification_id: Optional[str] = None
    created_by: Optional[str] = None


class SearchConversationDto(PageRequest, BaseQueryDto):
    type: Optional[str] = None
    verification_id: Optional[str] = None


class ConversationDto(Object):
    """Conversation-list item (§N.3). ``unread`` is the per-viewer count, filled by the
    service from the participant read state."""

    id: str
    type: ConversationType
    verification_id: Optional[str] = None
    subject: Optional[str] = None
    last_message_at: Optional[datetime] = None
    closed: bool = False
    unread: int = 0
