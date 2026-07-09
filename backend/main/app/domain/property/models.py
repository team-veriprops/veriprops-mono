"""Property domain (PRD §4.3) — thin, first-class, separate from Verification.

A property holds the customer-submitted facts (address, coordinates, type, details,
seller, documents). Verifications point at a property; re-checks/tier upgrades reuse
the same row. MVP does not auto-deduplicate — one row per submission is acceptable.
"""
from __future__ import annotations

import enum
from typing import List, Optional

from sqlalchemy import Column, Float, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import jsonb_variant


class PropertyType(str, enum.Enum):
    """PRD §5.1 step 1B."""

    LAND = "LAND"
    BUILDING = "BUILDING"


class Property(BaseEntity):
    __tablename__ = "properties"

    customer_id = Column(String(36), nullable=False, index=True)
    property_type = Column(String(16), nullable=False)
    address = Column(String(512), nullable=True)
    # Mandatory escape valve when Google Places can't resolve the plot (PRD §5.1 1C).
    landmark = Column(String(512), nullable=True)
    state = Column(String(64), nullable=True)
    lga = Column(String(64), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    place_id = Column(String(255), nullable=True)
    # Conditional facts (Land: size/use/survey status; Building: floors/age/occupancy/C-of-O).
    details = Column(MutableDict.as_mutable(jsonb_variant()), nullable=True)
    seller = Column(MutableDict.as_mutable(jsonb_variant()), nullable=True)
    documents = Column(MutableList.as_mutable(jsonb_variant()), nullable=True)
    # customer_id's index is declared inline (index=True) — it auto-names to
    # ix_properties_customer_id, matching the migration. Don't re-declare it here.


# ─── DTOs ─────────────────────────────────────────────────────────

class SellerInfoDto(Object):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship: Optional[str] = None
    notes: Optional[str] = None


class PropertyInputDto(Object):
    property_type: PropertyType
    address: Optional[str] = None
    landmark: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    details: Optional[dict] = None
    seller: Optional[SellerInfoDto] = None
    documents: Optional[List[dict]] = None


class CreatePropertyDto(Object):
    customer_id: str
    property_type: PropertyType
    address: Optional[str] = None
    landmark: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    details: Optional[dict] = None
    seller: Optional[dict] = None
    documents: Optional[List[dict]] = None


class UpdatePropertyDto(Object):
    property_type: Optional[str] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    details: Optional[dict] = None
    seller: Optional[dict] = None
    documents: Optional[List[dict]] = None


class SearchPropertyDto(InternalPageRequest, BaseQueryDto):
    customer_id: Optional[str] = None


class QueryPropertyDto(BaseQueryDto):
    customer_id: Optional[str] = None
    property_type: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None


class PropertyDto(Object):
    id: str
    property_type: PropertyType
    address: Optional[str] = None
    landmark: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
