"""Evidence domain models — PRD S22-S25 (agent evidence uploads)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Float, Integer, JSON, String, Text
from sqlalchemy.ext.mutable import MutableDict

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class EvidenceType(str, enum.Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"


# Nigeria bounding box for GPS validation
_NG_LAT_MIN, _NG_LAT_MAX = 4.0, 14.0
_NG_LNG_MIN, _NG_LNG_MAX = 3.0, 15.0


def is_in_nigeria(lat: float, lng: float) -> bool:
    return _NG_LAT_MIN <= lat <= _NG_LAT_MAX and _NG_LNG_MIN <= lng <= _NG_LNG_MAX


class EvidenceItem(BaseEntity):
    __tablename__ = "evidence_items"

    task_id = Column(String(36), nullable=False, index=True)
    uploader_id = Column(String(36), nullable=False, index=True)
    type = Column(String(16), nullable=False, default=EvidenceType.PHOTO.value)
    file_url = Column(String(512), nullable=False)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    captured_at = Column(UTCDateTime, nullable=True)
    metadata_ = Column("metadata", MutableDict.as_mutable(JSON), nullable=True)


class EvidenceItemDto(Object):
    id: str
    task_id: str
    uploader_id: str
    type: EvidenceType
    file_url: str
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    captured_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class CreateEvidenceItemDto(Object):
    task_id: str
    uploader_id: str
    type: EvidenceType = EvidenceType.PHOTO
    file_url: str
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    captured_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateEvidenceItemDto(Object):
    pass


class QueryEvidenceItemDto(BaseQueryDto):
    task_id: Optional[str] = None
    uploader_id: Optional[str] = None


class SearchEvidenceItemDto(PageRequest, BaseQueryDto):
    task_id: Optional[str] = None
    uploader_id: Optional[str] = None
