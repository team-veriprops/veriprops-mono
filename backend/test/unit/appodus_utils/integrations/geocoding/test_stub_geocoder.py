"""Deterministic geocoding stub (PRD §5.1) — reproducible NG fixtures for automation."""
from main.appodus_utils.integrations.geocoding.factory import GeocoderFactory
from main.appodus_utils.integrations.geocoding.models import GeoProvider
from main.appodus_utils.integrations.geocoding.stub.stub_geocoder import StubGeocoder


class TestStubGeocoder:
    async def test_autocomplete_filters_by_query(self):
        geo = StubGeocoder()
        results = await geo.autocomplete("lekki")
        assert len(results) == 1
        assert "Lekki" in results[0].description

    async def test_autocomplete_empty_returns_all(self):
        geo = StubGeocoder()
        assert len(await geo.autocomplete("")) >= 3

    async def test_geocode_resolves_place_id(self):
        geo = StubGeocoder()
        loc = await geo.geocode("stub-lekki")
        assert loc is not None
        assert loc.state == "Lagos"
        assert loc.latitude and loc.longitude

    async def test_reverse_geocode_returns_dragged_point(self):
        geo = StubGeocoder()
        loc = await geo.reverse_geocode(6.45, 3.47)
        assert loc is not None
        assert loc.latitude == 6.45  # keeps the dragged pin


class TestFactory:
    def test_default_active_provider_is_stub(self):
        factory = GeocoderFactory([StubGeocoder()])
        provider = factory.get_active_provider()
        assert provider.platform == GeoProvider.STUB
