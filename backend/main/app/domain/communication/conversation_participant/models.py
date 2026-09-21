"""Conversation participant domain (PRD §N.3, §26.8).

Per-user membership + read state for a thread. Backs the Chat counter (number of
conversations with unread messages) and the per-conversation unread badge: a participant
is unread when the thread's ``last_message_at`` is newer than the participant's
``last_read_at``. Opening a conversation stamps ``last_read_at`` and clears the badge.

A membership may also carry a **visibility window** (``visible_from`` / ``visible_until``).
It is what lets a customer see their WhatsApp thread in the portal safely: the thread is
keyed on a phone number, so messages from before they linked it may belong to a previous
holder of that number, and after they unlink it the thread keeps moving for the agents.
The window bounds what they can read; a closed window (``visible_until`` set) leaves them
read-only history. Web threads never set it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String, text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


def is_unread(
    last_message_at: Optional[datetime],
    last_read_at: Optional[datetime],
    visible_from: Optional[datetime] = None,
    visible_until: Optional[datetime] = None,
) -> bool:
    """Whether a thread shows as unread for one participant.

    The thread records only its latest message, so ``visible_until`` caps it as an upper
    bound on what the participant could have missed; a released thread with possibly-unread
    history stays unread until it is opened once. ``conversation_participant.repo.
    unread_condition`` applies the same rule in SQL — change both together.
    """
    if last_message_at is None:
        return False
    effective = min(last_message_at, visible_until) if visible_until else last_message_at
    if visible_from is not None and effective < visible_from:
        return False
    return last_read_at is None or last_read_at < effective


class ConversationParticipant(BaseEntity):
    __tablename__ = "conversation_participants"

    conversation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=True)  # the participant's role in the thread (CUSTOMER/ADMIN/AGENT role)
    last_read_at = Column(UTCDateTime, nullable=True)
    # The visibility window — see the module docstring. Null on both ends means the whole
    # thread, which is every web membership.
    visible_from = Column(UTCDateTime, nullable=True)
    visible_until = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_conv_participants_user", "user_id"),
        Index("ix_conv_participants_conversation", "conversation_id"),
        # One live membership per member: concurrent first opens must not both insert.
        Index(
            "uq_conv_participants_membership", "conversation_id", "user_id",
            unique=True, postgresql_where=text("deleted = FALSE"),
        ),
    )

    @property
    def is_read_only(self) -> bool:
        """A closed window: the member keeps their history but can no longer write."""
        return self.visible_until is not None


class CreateConversationParticipantDto(Object):
    conversation_id: str
    user_id: str
    role: Optional[str] = None
    last_read_at: Optional[datetime] = None
    visible_from: Optional[datetime] = None


class UpdateConversationParticipantDto(Object):
    role: Optional[str] = None


class QueryConversationParticipantDto(BaseQueryDto):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


class SearchConversationParticipantDto(InternalPageRequest, BaseQueryDto):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
