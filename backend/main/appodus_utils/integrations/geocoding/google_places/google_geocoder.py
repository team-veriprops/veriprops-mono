"""Google Places (New) geocoder (PRD §5.1 — the live provider, behind the facade).

Selected when settings.GEOCODING_PROVIDER == GOOGLE_PLACES. Instantiation is credential-free
so bootstrap can register every provider; the key is checked on the first real call.

* ``POST /places:autocomplete`` — suggestions for what the customer typed, Nigeria only.
* ``GET /places/{id}`` — the chosen place's address, state, LGA and coordinates.

The key goes in ``X-Goog-Api-Key`` (never a URL a log could print), and every call names its
fields in ``X-Goog-FieldMask``: Places bills by the fields asked for. A session token, when
the frontend sends one, groups one address search — its keystrokes and the place chosen — into
one billed session. Google's own error text is logged, never returned.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.config.settings import is_configured_secret
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.geocoding.interface import IGeocoder
from main.appodus_utils.integrations.geocoding.models import (
    GeoLocation,
    GeoProvider,
    GeoSuggestion,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di["logger"]

_AUTOCOMPLETE_FIELDS = "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text"
_DETAILS_FIELDS = "id,formattedAddress,location,addressComponents"
# Nigeria's first- and second-level divisions: the state and the LGA.
_STATE, _LGA = "administrative_area_level_1", "administrative_area_level_2"
_UNAVAILABLE = "Address search is not available right now. Type the address and a landmark instead."


class _NotFound(Exception):
    pass


@inject
class GooglePlacesGeocoder(IGeocoder):
    @property
    def platform(self) -> GeoProvider:
        return GeoProvider.GOOGLE_PLACES

    async def autocomplete(
        self, query: str, country: str = "NG", session_token: Optional[str] = None,
    ) -> List[GeoSuggestion]:
        body: Dict[str, Any] = {"input": query, "includedRegionCodes": [country.lower()]}
        if session_token:
            body["sessionToken"] = session_token
        data = await self._call("POST", "/places:autocomplete", _AUTOCOMPLETE_FIELDS, "suggest addresses", json=body)
        return [
            GeoSuggestion(place_id=p["placeId"], description=(p.get("text") or {}).get("text", ""))
            for p in (s.get("placePrediction") for s in data.get("suggestions") or [])
            if p and p.get("placeId")
        ]

    async def geocode(self, place_id: str, session_token: Optional[str] = None) -> Optional[GeoLocation]:
        params = {"sessionToken": session_token} if session_token else None
        try:
            data = await self._call(
                "GET", f"/places/{quote(place_id, safe='')}", _DETAILS_FIELDS, "look up the place", params=params,
            )
        except _NotFound:
            return None
        location = data.get("location") or {}
        if "latitude" not in location or "longitude" not in location:
            return None
        components = data.get("addressComponents") or []
        return GeoLocation(
            place_id=data.get("id") or place_id,
            address=data.get("formattedAddress") or "",
            state=_component(components, _STATE),
            lga=_component(components, _LGA),
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
        )

    async def _call(self, method: str, path: str, fields: str, action: str, **kwargs: Any) -> Dict[str, Any]:
        if not is_configured_secret(settings.GOOGLE_PLACES_API_KEY):
            logger.error("Google Places is the geocoder but GOOGLE_PLACES_API_KEY is not configured")
            raise IntegrationException(_UNAVAILABLE)
        client: httpx.AsyncClient = di[httpx.AsyncClient]
        try:
            response = await client.request(
                method, f"{settings.GOOGLE_PLACES_BASE_URL.rstrip('/')}{path}",
                headers={"X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY, "X-Goog-FieldMask": fields},
                **kwargs,
            )
        except httpx.HTTPError as e:
            logger.error(f"Google Places unreachable while trying to {action}: {e!r}")
            raise IntegrationException(_UNAVAILABLE) from e
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        # Only a 404 means "no such place": Google answers a bad key, field mask or session
        # token with a 400, which must be logged as the configuration fault it is.
        if response.status_code == 404 and method == "GET":
            raise _NotFound()
        if response.is_error:
            logger.error(
                f"Google Places refused to {action}: HTTP {response.status_code} "
                f"{(payload.get('error') or {}).get('status')!r}"
            )
            raise IntegrationException(_UNAVAILABLE)
        return payload


def _component(components: List[Dict[str, Any]], kind: str) -> Optional[str]:
    return next((c.get("longText") for c in components if kind in (c.get("types") or [])), None)
