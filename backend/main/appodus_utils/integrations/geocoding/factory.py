from typing import List

from kink import inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import settings
from main.appodus_utils.integrations.geocoding.interface import IGeocoder
from main.appodus_utils.integrations.geocoding.models import GeoProvider

di_bootstrap.register_all_subclasses(IGeocoder)


@inject
class GeocoderFactory:
    """Resolves the active geocoder from settings.GEOCODING_PROVIDER (Stub default)."""

    def __init__(self, providers: List[IGeocoder]):
        self._factory = {p.platform: p for p in providers}

    def get_active_provider(self) -> IGeocoder:
        return self._factory.get(GeoProvider(settings.GEOCODING_PROVIDER))
