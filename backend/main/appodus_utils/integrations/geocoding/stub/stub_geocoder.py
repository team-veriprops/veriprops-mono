"""Deterministic geocoding stub — the default provider in local/test/dev.

Returns fixed Nigerian suggestions/locations so autonomous QA is reproducible.
Never hits a network. Selected when settings.GEOCODING_PROVIDER == STUB.
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.appodus_utils.integrations.geocoding.interface import IGeocoder
from main.appodus_utils.integrations.geocoding.models import (
    GeoLocation,
    GeoProvider,
    GeoSuggestion,
)

# A small deterministic fixture set keyed by place_id.
_FIXTURES = {
    "stub-lekki": GeoLocation(
        place_id="stub-lekki", address="Lekki Phase 1, Lagos", state="Lagos", lga="Eti-Osa",
        latitude=6.4478, longitude=3.4723,
    ),
    "stub-maitama": GeoLocation(
        place_id="stub-maitama", address="Maitama, Abuja", state="FCT", lga="Abuja Municipal",
        latitude=9.0870, longitude=7.4980,
    ),
    "stub-gra-enugu": GeoLocation(
        place_id="stub-gra-enugu", address="GRA, Enugu", state="Enugu", lga="Enugu North",
        latitude=6.4483, longitude=7.5106,
    ),
}


@inject
class StubGeocoder(IGeocoder):
    @property
    def platform(self) -> GeoProvider:
        return GeoProvider.STUB

    async def autocomplete(self, query: str, country: str = "NG") -> List[GeoSuggestion]:
        q = (query or "").lower()
        return [
            GeoSuggestion(place_id=loc.place_id, description=loc.address)
            for loc in _FIXTURES.values()
            if not q or q in loc.address.lower()
        ]

    async def geocode(self, place_id: str) -> Optional[GeoLocation]:
        return _FIXTURES.get(place_id)

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeoLocation]:
        # Nearest fixture by naive distance — deterministic for a dragged pin.
        best = min(
            _FIXTURES.values(),
            key=lambda loc: (loc.latitude - latitude) ** 2 + (loc.longitude - longitude) ** 2,
        )
        return GeoLocation(
            place_id=None, address=best.address, state=best.state, lga=best.lga,
            latitude=latitude, longitude=longitude,
        )
