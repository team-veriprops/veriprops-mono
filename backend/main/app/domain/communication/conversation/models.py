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

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


class ConversationType(str, enum.Enum):
    """Who is talking in a thread (PRD §11.1, §4.6)."""

    CUSTOMER_ADMIN = "CUSTOMER_ADMIN"   # customer ↔ admin, one per verification
    ADMIN_AGENT = "ADMIN_AGENT"         # admin ↔ agent(s), one per verification, task-taggable
    GENERAL_SUPPORT = "GENERAL_SUPPORT"  # account/billing/general, one per user, no verification


class ConversationChannel(str, enum.Enum):
    """Which surface a thread originated on (PRD §26.3.1, §26.8).

    Deliberately separate from ``ConversationType``: type says *who* is talking, channel
    says *where* they started. §26.8 wants one conversation object per person across both
    surfaces, so a WhatsApp enquiry is an ordinary GENERAL_SUPPORT thread that happens to
    have arrived over WhatsApp — not a second kind of thread to reconcile later.
    """

    WEB = "WEB"
    WHATSAPP = "WHATSAPP"


class ConversationReadOnlyReason(str, enum.Enum):
    """Why a member may read a thread but no longer write to it."""

    # The WhatsApp number behind the thread was unlinked or released (§26.4.4): the history
    # up to that moment stays, but the thread no longer belongs to this account.
    NUMBER_UNLINKED = "NUMBER_UNLINKED"


class AdminInboxFilter(str, enum.Enum):
    """The facets of the admin Conversations inbox (§16.5). Each is a server-side scope on
    the one inbox query, so the list and its paging never drift from what the SQL counts."""

    SUPPORT = "SUPPORT"    # web general-support threads
    WHATSAPP = "WHATSAPP"  # threads that arrived over WhatsApp, linked to an account or not
    CASES = "CASES"        # the two verification threads: customer↔admin and admin↔agent


# ─── ORM ──────────────────────────────────────────────────────────

class Conversation(BaseEntity):
    __tablename__ = "conversations"

    type = Column(String(20), nullable=False)
    # Null for GENERAL_SUPPORT; set for the two verification-scoped channels.
    verification_id = Column(String(36), nullable=True, index=True)
    subject = Column(String(200), nullable=True)
    # ``created_by`` (the thread opener) is the inherited BaseEntity audit column. It is
    # null for a WhatsApp enquiry from a number not yet linked to an account (§26.4.4) —
    # the thread exists before we know who is on the other end.
    channel = Column(String(10), nullable=False, server_default=ConversationChannel.WEB.value)
    # The channel-native identity for a non-web thread: the sender's E.164 number. This
    # is how an inbound WhatsApp message finds its existing thread before linking.
    external_ref = Column(String(20), nullable=True)
    last_message_at = Column(UTCDateTime, nullable=True)
    closed = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("ix_conversations_verification", "verification_id"),
        Index("ix_conversations_external_ref", "external_ref"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateConversationDto(Object):
    type: ConversationType
    verification_id: Optional[str] = None
    subject: Optional[str] = None
    # Null for an inbound WhatsApp thread from an unlinked number (§26.4.4).
    created_by: Optional[str] = None
    channel: ConversationChannel = ConversationChannel.WEB
    external_ref: Optional[str] = None
    last_message_at: Optional[datetime] = None


class UpdateConversationDto(Object):
    subject: Optional[str] = None
    closed: Optional[bool] = None


class QueryConversationDto(BaseQueryDto):
    type: Optional[str] = None
    verification_id: Optional[str] = None
    created_by: Optional[str] = None


class SearchConversationDto(InternalPageRequest, BaseQueryDto):
    type: Optional[str] = None
    verification_id: Optional[str] = None


class ConversationDto(Object):
    """Conversation-list item (§N.3). ``unread`` is the per-viewer count, filled by the
    service from the participant read state."""

    id: str
    type: ConversationType
    verification_id: Optional[str] = None
    subject: Optional[str] = None
    # Lets the admin console label where a thread came from (§26.3.3 source labeling).
    channel: ConversationChannel = ConversationChannel.WEB
    external_ref: Optional[str] = None
    last_message_at: Optional[datetime] = None
    closed: bool = False
    unread: int = 0
    # Per viewer, from their membership's visibility window: the history stays readable
    # but the composer is closed, and the reason says why.
    read_only: bool = False
    read_only_reason: Optional[ConversationReadOnlyReason] = None
    # The account a support thread belongs to, for the admin console only: admins work
    # threads they are not members of, and a web support thread has no other identity.
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    # A web turn is waiting for the assistant's intent model (D93): the client shows the
    # assistant typing and asks for the turn, which is how a reload mid-turn recovers.
    assistant_pending: bool = False
