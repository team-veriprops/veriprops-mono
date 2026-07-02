"""Geocoding provider facade (PRD §5.1). Swappable via settings.GEOCODING_PROVIDER."""
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
    async def autocomplete(self, query: str, country: str = "NG") -> List[GeoSuggestion]:
        ...

    @abstractmethod
    async def geocode(self, place_id: str) -> Optional[GeoLocation]:
        ...

    @abstractmethod
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeoLocation]:
        ...
