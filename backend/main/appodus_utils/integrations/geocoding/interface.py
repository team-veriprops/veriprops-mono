"""Geocoding provider facade (PRD §5.1). Swappable via settings.GEOCODING_PROVIDER.

``session_token`` groups one address search — its keystrokes and the place finally chosen —
into one billed session with a live provider; a provider without sessions ignores it.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from main.appodus_utils.integrations.geocoding.models import (
    GeoLocation,
    GeoProvider,
    GeoSuggestion,
)


class IGeocoder(ABC):
    @property
    @abstractmethod
    def platform(self) -> GeoProvider:
        ...

    @abstractmethod
    async def autocomplete(
        self, query: str, country: str = "NG", session_token: Optional[str] = None,
    ) -> List[GeoSuggestion]:
        ...

    @abstractmethod
    async def geocode(self, place_id: str, session_token: Optional[str] = None) -> Optional[GeoLocation]:
        ...
