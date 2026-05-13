"""Escalation domain models — PRD S27 (agent issue escalation)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class EscalationCategory(str, enum.Enum):
    INACCESSIBLE = "INACCESSIBLE"
    SUSPICIOUS = "SUSPICIOUS"
    SAFETY = "SAFETY"
    CONFLICTING = "CONFLICTING"
    OTHER = "OTHER"


class Escalation(BaseEntity):
    __tablename__ = "escalations"

    task_id = Column(String(36), nullable=False, index=True)
    reporter_id = Column(String(36), nullable=False, index=True)
    category = Column(String(32), nullable=False)
    description = Column(Text, nullable=False)


class EscalationDto(Object):
    id: str
    task_id: str
    reporter_id: str
    category: EscalationCategory
    description: str
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateEscalationDto(Object):
    task_id: str
    reporter_id: str
    category: EscalationCategory
    description: str


class UpdateEscalationDto(Object):
    pass


class QueryEscalationDto(BaseQueryDto):
    task_id: Optional[str] = None
    reporter_id: Optional[str] = None


class SearchEscalationDto(PageRequest, BaseQueryDto):
    task_id: Optional[str] = None
    reporter_id: Optional[str] = None


class ReportEscalationDto(Object):
    category: EscalationCategory
    description: str
