"""Listing-URL parser models — PRD §5.2 (R5.2)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from main.appodus_utils import Object


class ParsedListingDto(Object):
    """Fields extracted from a property listing URL. All fields are optional
    because parsers only populate what they can reliably extract."""
    property_type: Optional[str] = None       # "LAND" | "BUILDING"
    state: Optional[str] = None               # Nigerian state, upper-cased
    lga: Optional[str] = None
    address_line: Optional[str] = None
    price_minor: Optional[int] = None         # NGN kobo
    title: Optional[str] = None
    source_url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None  # bedrooms, bathrooms, size_sqm, etc.


class ParseResultDto(Object):
    success: bool
    data: Optional[ParsedListingDto] = None
    error_message: Optional[str] = None


class ParseListingRequest(Object):
    url: str
