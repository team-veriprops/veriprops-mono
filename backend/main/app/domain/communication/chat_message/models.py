"""Chat message domain (PRD §11.1, §11.2, §4.7).

A message in a thread. Carries the §4.7 fraud-hold state (``ChatMessageState``), an optional
``task_id`` tag (Admin↔Agent messages about a specific role), a ``message_kind`` that
distinguishes ordinary chat from platform auto-posts, and the fraud categories that held it
(for instrumentation).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Index, String, Text

from main.app.config.settings import settings
from main.app.core.state.status import ChatMessageState
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

# Chat message body cap — backend is the source of truth; the frontend reads the same
# value via /config/public rather than hardcoding its own input maxLength.
BODY_MAX_LENGTH = settings.CHAT_MESSAGE_MAX_LENGTH


class MessageKind(str, enum.Enum):
    """What a message is (PRD §11.1).

    Server-owned: every human message is ``CHAT``, and only platform callers write
    ``SYSTEM_AUTO`` — which is what exempts their copy from the §4.7 fraud scan.
    """

    # TODO(gap): structured customer↔agent clarifications — relay a customer's question to
    # the assigned agent, carry the answer back, track OPEN→ANSWERED — PRD "Known Gaps & Roadmap".
    CHAT = "CHAT"                                # ordinary person-to-person message
    SYSTEM_AUTO = "SYSTEM_AUTO"                  # auto-posted status change / rejection reason / bot reply


class MessageSource(str, enum.Enum):
    """Which surface a message arrived on (PRD §26.3.3 source labeling, §26.8).

    Orthogonal to ``SenderKind``: the same customer can speak from either surface, and
    the admin console shows which one so a reply goes back the right way.
    """

    WEB = "WEB"
    WHATSAPP = "WHATSAPP"


class ChannelDeliveryStatus(str, enum.Enum):
    """How far a message has travelled over its conversation's own channel (§26.3.3, D92).

    Only a message that leaves over WhatsApp has one. The first three come from Meta's
    receipts; ``CANCELLED`` is ours — a queued reply the customer already read in the portal,
    which therefore never goes to their phone.
    """

    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_STATUS_PROGRESS = {
    ChannelDeliveryStatus.SENT.value: 1,
    ChannelDeliveryStatus.DELIVERED.value: 2,
    ChannelDeliveryStatus.READ.value: 3,
}


def advance_channel_status(current: Optional[str], new: ChannelDeliveryStatus) -> bool:
    """Whether a receipt for *new* should replace the stored *current* status.

    Meta delivers receipts out of order and redelivers them, so a status only moves forward:
    a late ``DELIVERED`` never undoes ``READ``. ``FAILED`` is recorded only over nothing or
    ``SENT`` — a message that arrived stays arrived — and is itself superseded by proof of
    arrival. A ``CANCELLED`` message was never sent, so nothing can follow it.
    """
    if current == ChannelDeliveryStatus.CANCELLED.value:
        return False
    if new == ChannelDeliveryStatus.CANCELLED:
        return current is None
    if new == ChannelDeliveryStatus.FAILED:
        return current in (None, ChannelDeliveryStatus.SENT.value)
    if current == ChannelDeliveryStatus.FAILED.value:
        return new in (ChannelDeliveryStatus.DELIVERED, ChannelDeliveryStatus.READ)
    return _STATUS_PROGRESS[new.value] > _STATUS_PROGRESS.get(current or "", 0)


class SenderKind(str, enum.Enum):
    """Which side sent a message — used to gate the customer identity projection (§11.3)."""

    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


# ─── ORM ──────────────────────────────────────────────────────────

class ChatMessage(BaseEntity):
    __tablename__ = "chat_messages"

    conversation_id = Column(String(36), nullable=False, index=True)
    sender_user_id = Column(String(36), nullable=True)  # null for SYSTEM auto-posts
    sender_kind = Column(String(16), nullable=False, server_default=SenderKind.SYSTEM.value)
    source = Column(String(10), nullable=False, server_default=MessageSource.WEB.value)
    # The channel-native id (Meta's wamid) for a message that came from or went to
    # WhatsApp — the audit trail back to the raw inbound record.
    external_message_id = Column(String(128), nullable=True)
    body = Column(Text, nullable=False)
    # Admin↔Agent task tag (§11.1) — which role's work this message is about.
    task_id = Column(String(36), nullable=True, index=True)
    state = Column(String(20), nullable=False, server_default=ChatMessageState.PENDING_SCAN.value)
    message_kind = Column(String(24), nullable=False, server_default=MessageKind.CHAT.value)
    # §4.7 fraud categories that held the message (empty for a clean fast-lane message).
    flagged_categories = Column(JSONB_VARIANT, nullable=True)
    # Attachment storage refs — column kept forward-compat; no upload wired this slice (D22).
    # TODO(gap): chat attachments — wire presigned upload (reuse the storage facade) + UI —
    # PRD "Known Gaps & Roadmap".
    attachments = Column(JSONB_VARIANT, nullable=True)
    delivered_at = Column(UTCDateTime, nullable=True)
    # When the message actually left over the conversation's own channel (§26.7). Distinct
    # from `delivered_at`, which means "released past the fraud hold": an agent's reply
    # typed outside Meta's 24-hour window is DELIVERED in the thread and still queued
    # here, and that is exactly the state the console has to be able to show.
    channel_delivered_at = Column(UTCDateTime, nullable=True)
    # A `ChannelDeliveryStatus`, moved forward by Meta's receipts, and when it last moved.
    channel_status = Column(String(12), nullable=True)
    channel_status_at = Column(UTCDateTime, nullable=True)
    # What a non-text WhatsApp inbound actually was (§26.6.3) — the console reads it to
    # flag an image as unofficial and a voice note as audio.
    media_kind = Column(String(16), nullable=True)
    held_at = Column(UTCDateTime, nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_chat_messages_conversation", "conversation_id"),
        Index("ix_chat_messages_state", "state"),
        # The queue read is "this thread's undelivered agent replies" (§26.7 flush).
        Index("ix_chat_messages_channel_pending", "conversation_id", "channel_delivered_at"),
        # A receipt finds its message by the wamid Meta returned when we sent it.
        Index("ix_chat_messages_external_message_id", "external_message_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateChatMessageDto(Object):
    conversation_id: str
    sender_user_id: Optional[str] = None
    sender_kind: SenderKind
    source: MessageSource = MessageSource.WEB
    external_message_id: Optional[str] = None
    body: str
    task_id: Optional[str] = None
    state: ChatMessageState = ChatMessageState.PENDING_SCAN
    message_kind: MessageKind = MessageKind.CHAT
    flagged_categories: Optional[List[str]] = None
    media_kind: Optional[InboundKind] = None
    delivered_at: Optional[datetime] = None
    held_at: Optional[datetime] = None


class UpdateChatMessageDto(Object):
    state: Optional[str] = None
    reviewed_by: Optional[str] = None


class QueryChatMessageDto(BaseQueryDto):
    conversation_id: Optional[str] = None
    state: Optional[str] = None
    task_id: Optional[str] = None


class SearchChatMessageDto(InternalPageRequest, BaseQueryDto):
    conversation_id: Optional[str] = None
    state: Optional[str] = None


# ─── API response DTOs ────────────────────────────────────────────

class ChatSenderDto(Object):
    """Customer-safe sender identity (§11.3). For an agent this is first name + role only —
    never last name, email, or phone."""

    user_id: Optional[str] = None
    kind: SenderKind
    first_name: Optional[str] = None
    role: Optional[str] = None
    avatar_url: Optional[str] = None


class ChatMessageDto(Object):
    id: str
    conversation_id: str
    body: str
    task_id: Optional[str] = None
    state: ChatMessageState
    message_kind: MessageKind
    source: MessageSource = MessageSource.WEB
    sender: ChatSenderDto
    held_notice: Optional[str] = None  # sender-facing "being checked" copy while HELD (§11.2)
    date_created: datetime
    delivered_at: Optional[datetime] = None
    # §26.6.3 — what arrived, when it was not text. `unofficial_media` is *derived* from it
    # rather than stored: the evidence rule (§26.1.6) says chat media is never canonical, so
    # a persisted boolean could only ever disagree with the rule it is meant to express.
    media_kind: Optional[InboundKind] = None
    unofficial_media: bool = False
    # An agent reply that is in the thread but has not left over WhatsApp yet, because it
    # was typed outside Meta's 24-hour window (§26.7). It goes out on the customer's next
    # message; until then the console has to say so, or the agent believes it sent.
    pending_channel_delivery: bool = False
    # Console only: how far the message got on the customer's phone (sent/delivered/read).
    channel_status: Optional[ChannelDeliveryStatus] = None
    # Customer only: an admin has read the thread past this message of theirs.
    seen_by_support: bool = False
    # On a send's response only (D93): the assistant's inline answer to this message, or
    # that one is still coming because it needs the intent model.
    assistant_reply: Optional["ChatMessageDto"] = None
    assistant_pending: bool = False


ChatMessageDto.model_rebuild()


class HeldMessageDto(Object):
    """Admin hold-review queue item (§11.2) — includes the raw body + why it was held."""

    id: str
    conversation_id: str
    conversation_type: Optional[str] = None
    verification_id: Optional[str] = None
    sender_user_id: Optional[str] = None
    sender_kind: SenderKind
    source: MessageSource = MessageSource.WEB
    body: str
    flagged_categories: List[str] = []
    held_at: Optional[datetime] = None
    date_created: datetime
