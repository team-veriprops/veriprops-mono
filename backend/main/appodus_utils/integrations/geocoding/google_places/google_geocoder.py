"""Google Places geocoder (PRD §5.1 — primary real provider, behind the facade).

Selected only when settings.GEOCODING_PROVIDER == GOOGLE_PLACES. Instantiation is
credential-free so bootstrap can register every provider subclass; the live Places
calls are gated pending credentials/testing. Local/test/dev use StubGeocoder.
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.appodus_utils.exception.exceptions import AppodusBaseException
from main.appodus_utils.integrations.geocoding.interface import IGeocoder
from main.appodus_utils.integrations.geocoding.models import (
    GeoLocation,
    GeoProvider,
    GeoSuggestion,
)


@inject
class GooglePlacesGeocoder(IGeocoder):
    @property
    def platform(self) -> GeoProvider:
        return GeoProvider.GOOGLE_PLACES

    def _not_enabled(self):
        raise AppodusBaseException(
            message="Google Places geocoding is not yet enabled; set GEOCODING_PROVIDER=STUB for automation.",
        )

    async def autocomplete(self, query: str, country: str = "NG") -> List[GeoSuggestion]:
        self._not_enabled()

    async def geocode(self, place_id: str) -> Optional[GeoLocation]:
        self._not_enabled()

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeoLocation]:
        self._not_enabled()
