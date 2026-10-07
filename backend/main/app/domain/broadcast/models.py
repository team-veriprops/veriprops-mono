"""Broadcast domain (PRD §18.1, D37) — an admin announcement to an audience.

A broadcast targets an audience (All / Admins / Customers / Agents) and is sent immediately or
at a scheduled time. Sending claims it DRAFT/SCHEDULED → SENDING and records the audience size;
the fan-out then walks the audience in keyset pages (`fanout_cursor` = the last user id sent),
each page one in-app notification + one queued email per recipient through the §4.8 event bus.
The last page moves it to SENT. Cancelling a SENDING broadcast stops the pages not yet sent.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Dict, FrozenSet, List, Optional

from sqlalchemy import Column, Index, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


class BroadcastAudience(str, enum.Enum):
    ALL = "ALL"
    ADMINS = "ADMINS"
    CUSTOMERS = "CUSTOMERS"
    AGENTS = "AGENTS"


class BroadcastStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"      # claimed; the fan-out is reaching its audience page by page
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class BroadcastAction(str, enum.Enum):
    """What an admin may do to a broadcast; the screen offers exactly these."""

    SEND = "SEND"
    CANCEL = "CANCEL"


# The statuses each action may start from — the one table both the service's claims and the
# DTO's `allowed_actions` read, so a screen never offers a move the service would refuse.
ACTION_FROM_STATUSES: Dict[BroadcastAction, FrozenSet[BroadcastStatus]] = {
    BroadcastAction.SEND: frozenset({BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED}),
    BroadcastAction.CANCEL: frozenset({BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED, BroadcastStatus.SENDING}),
}


def allowed_actions(status: BroadcastStatus) -> List[BroadcastAction]:
    return [action for action, sources in ACTION_FROM_STATUSES.items() if status in sources]


# ─── ORM ──────────────────────────────────────────────────────────

class Broadcast(BaseEntity):
    __tablename__ = "broadcasts"

    audience = Column(String(16), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default=BroadcastStatus.DRAFT.value, index=True)
    scheduled_at = Column(UTCDateTime, nullable=True)
    sent_at = Column(UTCDateTime, nullable=True)
    # The audience size, counted when sending began.
    recipient_count = Column(Integer, nullable=False, server_default="0")
    # Recipients the fan-out has reached so far, and the last user id it sent to (keyset cursor).
    recipients_enqueued = Column(Integer, nullable=False, default=0, server_default="0")
    fanout_cursor = Column(String(36), nullable=True)
    # created_by (the composing admin) is inherited from BaseEntity — set via the create DTO.
    # status index is declared inline (index=True) → ix_broadcasts_status, matching the migration.

    __table_args__ = (
        # Inherited columns cannot take index=True here, so the admin index is declared here.
        Index("ix_broadcasts_created_by", "created_by"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateBroadcastDto(Object):
    audience: str
    subject: str
    body: str
    status: BroadcastStatus = BroadcastStatus.DRAFT
    scheduled_at: Optional[datetime] = None
    created_by: str


class UpdateBroadcastDto(Object):
    status: Optional[str] = None
    recipient_count: Optional[int] = None


class QueryBroadcastDto(BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


class SearchBroadcastDto(InternalPageRequest, BaseQueryDto):
    status: Optional[str] = None
    audience: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class ComposeBroadcastDto(Object):
    """Create a broadcast (§18.1). ``scheduled_at`` present → SCHEDULED; absent → DRAFT."""

    audience: BroadcastAudience
    subject: str
    body: str
    scheduled_at: Optional[datetime] = None


class BroadcastPreviewDto(Object):
    audience: BroadcastAudience
    recipient_count: int


class BroadcastDto(Object):
    id: str
    audience: BroadcastAudience
    subject: str
    body: str
    status: BroadcastStatus
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    recipient_count: int = 0
    recipients_enqueued: int = 0
    allowed_actions: List[BroadcastAction] = []
    date_created: datetime
