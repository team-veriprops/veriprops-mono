"""Property entity — captured by the customer wizard (PRD §5.1)."""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Float, Index, JSON, String, Text
from sqlalchemy.ext.mutable import MutableList

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class PropertySource(str, enum.Enum):
    MANUAL = "MANUAL"
    LISTING_URL = "LISTING_URL"


class PropertyType(str, enum.Enum):
    LAND = "LAND"
    BUILDING = "BUILDING"


class Property(BaseEntity):
    __tablename__ = "properties"

    source = Column(String(16), nullable=False, default=PropertySource.MANUAL.value)
    source_url = Column(String(1024), nullable=True)
    parsed_listing_data = Column(Text, nullable=True)  # JSON-encoded listing parse result
    property_type = Column(String(16), nullable=False)
    state = Column(String(64), nullable=False)
    lga = Column(String(128), nullable=True)
    address_line = Column(String(512), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    landmark_description = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # type-specific JSON
    documents = Column(MutableList.as_mutable(JSON), nullable=False, default=list)
    seller_info = Column(Text, nullable=True)  # JSON

    __table_args__ = (
        Index("ix_properties_state_lga", "state", "lga"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────


class CreatePropertyDto(Object):
    source: PropertySource = PropertySource.MANUAL
    source_url: Optional[str] = None
    property_type: PropertyType
    state: str
    lga: Optional[str] = None
    address_line: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    landmark_description: Optional[str] = None
    details: Optional[str] = None
    documents: List[str] = []
    seller_info: Optional[str] = None


class UpdatePropertyDto(Object):
    source: Optional[PropertySource] = None
    source_url: Optional[str] = None
    parsed_listing_data: Optional[str] = None
    property_type: Optional[PropertyType] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    address_line: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    landmark_description: Optional[str] = None
    details: Optional[str] = None
    documents: Optional[List[str]] = None
    seller_info: Optional[str] = None


class SearchPropertyDto(PageRequest, BaseQueryDto):
    state: Optional[str] = None
    lga: Optional[str] = None
    property_type: Optional[str] = None


class QueryPropertyDto(BaseQueryDto):
    state: Optional[str] = None
    lga: Optional[str] = None
    property_type: Optional[str] = None


class PropertyDto(Object):
    id: str
    source: PropertySource
    property_type: PropertyType
    state: str
    lga: Optional[str] = None
    address_line: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    landmark_description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    documents: List[str] = []
    seller_info: Optional[Dict[str, Any]] = None
