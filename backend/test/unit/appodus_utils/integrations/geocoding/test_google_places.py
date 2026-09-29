"""Live Google Places (New) contract, pinned against Google's documented HTTP shapes.

CI and e2e never reach Google (GEOCODING_PROVIDER=STUB), so these respx tests hold the
adapter to what Places (New) accepts:

* the key travels in `X-Goog-Api-Key`, never in a URL a log could print;
* every call names its fields (`X-Goog-FieldMask`) — Places bills by the fields asked for,
  and returns none without a mask;
* suggestions are restricted to Nigeria;
* one session token groups the keystrokes and the chosen place into one billed session;
* Google's own error text never leaves the adapter.
"""
import json

import httpx
import pytest
import respx

from main.app.config.settings import settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.geocoding.google_places.google_geocoder import GooglePlacesGeocoder

PLACES = "https://places.googleapis.test/v1"


@pytest.fixture(autouse=True)
def places_settings(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PLACES_BASE_URL", PLACES)
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "AIza-test-key")


class TestAutocomplete:
    @respx.mock
    async def test_suggestions_are_restricted_to_nigeria_and_carry_the_session(self):
        route = respx.post(f"{PLACES}/places:autocomplete").mock(return_value=httpx.Response(200, json={
            "suggestions": [
                {"placePrediction": {"placeId": "ChIJ-lekki", "text": {"text": "Lekki Phase 1, Lagos, Nigeria"}}},
                {"queryPrediction": {"text": {"text": "lekki restaurants"}}},
            ],
        }))

        suggestions = await GooglePlacesGeocoder().autocomplete("Lekki", country="NG", session_token="sess-1")

        assert [(s.place_id, s.description) for s in suggestions] == [("ChIJ-lekki", "Lekki Phase 1, Lagos, Nigeria")]
        request = route.calls.last.request
        assert json.loads(request.content) == {"input": "Lekki", "includedRegionCodes": ["ng"], "sessionToken": "sess-1"}
        assert request.headers["x-goog-api-key"] == "AIza-test-key"
        assert "placePrediction.placeId" in request.headers["x-goog-fieldmask"]
        assert "AIza" not in str(request.url)

    @respx.mock
    async def test_no_suggestions_is_an_empty_list(self):
        respx.post(f"{PLACES}/places:autocomplete").mock(return_value=httpx.Response(200, json={}))

        assert await GooglePlacesGeocoder().autocomplete("zzzz") == []

    @respx.mock
    async def test_a_session_token_is_optional(self):
        route = respx.post(f"{PLACES}/places:autocomplete").mock(return_value=httpx.Response(200, json={}))

        await GooglePlacesGeocoder().autocomplete("Ikeja")

        assert "sessionToken" not in json.loads(route.calls.last.request.content)


class TestPlaceDetails:
    @respx.mock
    async def test_a_place_resolves_to_its_address_state_lga_and_coordinates(self):
        route = respx.get(f"{PLACES}/places/ChIJ-lekki").mock(return_value=httpx.Response(200, json={
            "id": "ChIJ-lekki",
            "formattedAddress": "Lekki Phase 1, Lekki 106104, Lagos, Nigeria",
            "location": {"latitude": 6.4478, "longitude": 3.4723},
            "addressComponents": [
                {"longText": "Lekki Phase 1", "shortText": "Lekki Phase 1", "types": ["sublocality"]},
                {"longText": "Eti-Osa", "shortText": "Eti-Osa", "types": ["administrative_area_level_2", "political"]},
                {"longText": "Lagos", "shortText": "LA", "types": ["administrative_area_level_1", "political"]},
                {"longText": "Nigeria", "shortText": "NG", "types": ["country", "political"]},
            ],
        }))

        location = await GooglePlacesGeocoder().geocode("ChIJ-lekki", session_token="sess-1")

        assert (location.place_id, location.address, location.state, location.lga) == (
            "ChIJ-lekki", "Lekki Phase 1, Lekki 106104, Lagos, Nigeria", "Lagos", "Eti-Osa",
        )
        assert (location.latitude, location.longitude) == (6.4478, 3.4723)
        request = route.calls.last.request
        assert request.url.params["sessionToken"] == "sess-1"
        assert set(request.headers["x-goog-fieldmask"].split(",")) == {
            "id", "formattedAddress", "location", "addressComponents",
        }

    @respx.mock
    async def test_a_place_id_cannot_alter_the_path(self):
        route = respx.get(url__regex=rf"{PLACES}/places/.*").mock(return_value=httpx.Response(404, json={}))

        await GooglePlacesGeocoder().geocode("../../x?key=1")

        # What goes on the wire: one escaped path segment, no traversal and no query.
        assert route.calls.last.request.url.raw_path == b"/v1/places/..%2F..%2Fx%3Fkey%3D1"

    @respx.mock
    async def test_a_place_google_does_not_know_is_none(self):
        respx.get(f"{PLACES}/places/gone").mock(return_value=httpx.Response(404, json={
            "error": {"code": 404, "message": "Not found: places/gone", "status": "NOT_FOUND"},
        }))

        assert await GooglePlacesGeocoder().geocode("gone") is None

    @respx.mock
    async def test_a_bad_request_is_a_configuration_fault_not_a_missing_place(self):
        respx.get(f"{PLACES}/places/ChIJ-x").mock(return_value=httpx.Response(400, json={
            "error": {"code": 400, "message": "Invalid field mask", "status": "INVALID_ARGUMENT"},
        }))

        with pytest.raises(IntegrationException):
            await GooglePlacesGeocoder().geocode("ChIJ-x")


class TestFailures:
    @pytest.mark.parametrize("status", [403, 429, 500])
    @respx.mock
    async def test_a_refusal_or_outage_is_a_safe_integration_error(self, status):
        respx.post(f"{PLACES}/places:autocomplete").mock(return_value=httpx.Response(status, json={
            "error": {"message": "API key not valid. Please pass a valid API key.", "status": "PERMISSION_DENIED"},
        }))

        with pytest.raises(IntegrationException) as exc:
            await GooglePlacesGeocoder().autocomplete("Lekki")
        assert "API key" not in str(exc.value)

    @respx.mock
    async def test_an_unreachable_google_is_an_integration_error(self):
        respx.post(f"{PLACES}/places:autocomplete").mock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(IntegrationException):
            await GooglePlacesGeocoder().autocomplete("Lekki")

    async def test_an_unconfigured_key_is_an_integration_error(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "CHANGE_ME")

        with pytest.raises(IntegrationException):
            await GooglePlacesGeocoder().autocomplete("Lekki")
