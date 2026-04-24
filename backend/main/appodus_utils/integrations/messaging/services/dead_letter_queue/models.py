import enum
from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import Column, String, JSON, Integer, DateTime

from main.appodus_utils import BaseEntity, PageRequest, BaseQueryDto, Object
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.models import MessageChannel


class DLQStatus(str, enum.Enum):
    PENDING = "PENDING"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    PROCESSED = "PROCESSED"


class DLQ(BaseEntity):
    __tablename__ = 'dlq_entries'
    original_message = Column(JSON, nullable=False)
    channel = Column(String(20), nullable=False)
    provider = Column(String(50), nullable=False)
    error = Column(String(500), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime, nullable=False)
    status = Column(String(15), default="pending", nullable=False)
    extras = Column(JSON, default={})


class DLQBaseDto(Object):
    pass


class CreateDLQDto(DLQBaseDto):
    original_message: UpsertMessageDto
    channel: MessageChannel
    provider: str
    error: str
    attempts: int
    next_retry_at: datetime
    status: DLQStatus
    extras: Dict


class UpdateDLQDto(DLQBaseDto):
    pass


class _UpdateDLQDto(Object):
    error: Optional[str] = None
    attempts: Optional[int] = None
    next_retry_at: Optional[datetime] = None
    status: Optional[DLQStatus] = None


class SearchDLQDto(PageRequest, BaseQueryDto, _UpdateDLQDto):
    channel: Optional[str]
    provider: Optional[str]


class QueryDLQDto(DLQBaseDto, BaseQueryDto, _UpdateDLQDto):
    pass
