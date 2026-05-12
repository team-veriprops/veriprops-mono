"""Thread & message models — PRD Phase 11 (S37)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, Index, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ThreadType(str, enum.Enum):
    CUSTOMER_ADMIN = "CUSTOMER_ADMIN"
    ADMIN_AGENT = "ADMIN_AGENT"


class MessageType(str, enum.Enum):
    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    ATTACHMENT = "ATTACHMENT"


class SenderRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


# ─── ORM ──────────────────────────────────────────────────────────

class MessageThread(BaseEntity):
    __tablename__ = "message_threads"

    thread_type = Column(String(20), nullable=False, index=True)
    verification_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)

    __table_args__ = (
        Index("ix_threads_verification_type", "verification_id", "thread_type"),
    )


class ThreadMessage(BaseEntity):
    __tablename__ = "thread_messages"

    thread_id = Column(String(36), nullable=False, index=True)
    sender_id = Column(String(36), nullable=True)
    sender_role = Column(String(16), nullable=False, default=SenderRole.SYSTEM.value)
    message_type = Column(String(16), nullable=False, default=MessageType.TEXT.value)
    body = Column(Text, nullable=False)
    attachment_key = Column(String(512), nullable=True)
    is_held = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_thread_messages_thread_id", "thread_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class ThreadDto(Object):
    id: str
    thread_type: ThreadType
    verification_id: str
    task_id: Optional[str] = None
    created_at: datetime


class ThreadMessageDto(Object):
    id: str
    thread_id: str
    sender_id: Optional[str] = None
    sender_role: SenderRole
    message_type: MessageType
    body: str
    attachment_key: Optional[str] = None
    is_held: bool = False
    created_at: datetime


class CreateThreadDto(Object):
    thread_type: ThreadType
    verification_id: str
    task_id: Optional[str] = None


class CreateThreadMessageDto(Object):
    thread_id: str
    sender_id: Optional[str]
    sender_role: SenderRole
    message_type: MessageType = MessageType.TEXT
    body: str
    attachment_key: Optional[str] = None
    is_held: bool = False


class QueryThreadDto(BaseQueryDto):
    verification_id: Optional[str] = None
    thread_type: Optional[str] = None


class SearchThreadDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    thread_type: Optional[str] = None


class QueryThreadMessageDto(BaseQueryDto):
    thread_id: Optional[str] = None
    is_held: Optional[bool] = None


class SearchThreadMessageDto(PageRequest, BaseQueryDto):
    thread_id: Optional[str] = None
    is_held: Optional[bool] = None


class PostMessageDto(Object):
    body: str
    attachment_key: Optional[str] = None


class UpdateThreadMessageDto(Object):
    is_held: Optional[bool] = None
    body: Optional[str] = None
