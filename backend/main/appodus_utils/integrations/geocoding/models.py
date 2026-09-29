"""Geocoding facade DTOs (PRD §5.1).

Nigeria-restricted address resolution behind a swappable provider. Google Places
has weak coverage of informal/peri-urban plots, so the landmark free-text field is
a mandatory escape valve at the domain layer — geocoding is never a hard gate.
"""
from __future__ import annotations

from typing import Optional

from main.appodus_utils import Object
# Re-exported: the selector enum lives beside Settings, which cannot import this package.
from main.appodus_utils.config.providers import GeoProvider  # noqa: F401


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
