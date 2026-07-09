"""Geocoding facade DTOs (PRD §5.1).

Nigeria-restricted address resolution behind a swappable provider. Google Places
has weak coverage of informal/peri-urban plots, so the landmark free-text field is
a mandatory escape valve at the domain layer — geocoding is never a hard gate.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.appodus_utils import Object


class GeoProvider(str, enum.Enum):
    STUB = "STUB"
    GOOGLE_PLACES = "GOOGLE_PLACES"


class GeoSuggestion(Object):
    place_id: str
    description: str


class GeoLocation(Object):
    place_id: Optional[str] = None
    address: str
    state: Optional[str] = None
    lga: Optional[str] = None
    latitude: float
    longitude: float
