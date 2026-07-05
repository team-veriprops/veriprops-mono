"""Conversation participant domain (PRD §N.3).

Per-user membership + read state for a thread. Backs the Chat counter (number of
conversations with unread messages) and the per-conversation unread badge: a participant
is unread when the thread's ``last_message_at`` is newer than the participant's
``last_read_at``. Opening a conversation stamps ``last_read_at`` and clears the badge.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ConversationParticipant(BaseEntity):
    __tablename__ = "conversation_participants"

    conversation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=True)  # the participant's role in the thread (CUSTOMER/ADMIN/AGENT role)
    last_read_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_conv_participants_user", "user_id"),
        Index("ix_conv_participants_conversation", "conversation_id"),
    )


class CreateConversationParticipantDto(Object):
    conversation_id: str
    user_id: str
    role: Optional[str] = None
    last_read_at: Optional[datetime] = None


class UpdateConversationParticipantDto(Object):
    role: Optional[str] = None


class QueryConversationParticipantDto(BaseQueryDto):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


class SearchConversationParticipantDto(PageRequest, BaseQueryDto):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
