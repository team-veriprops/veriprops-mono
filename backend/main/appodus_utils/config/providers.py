"""Selectable providers whose choice is a setting.

A leaf module — it imports nothing of the app — so `Settings` can type its selectors with these
enums, and the integration packages (which import the `settings` singleton) can re-export them,
without an import cycle.
"""
import enum


class KycProvider(str, enum.Enum):
    """Selectable KYC backend (settings.KYC_PROVIDER)."""

    STUB = "STUB"
    DOJAH = "DOJAH"


class GeoProvider(str, enum.Enum):
    """Selectable geocoder (settings.GEOCODING_PROVIDER)."""

    STUB = "STUB"
    GOOGLE_PLACES = "GOOGLE_PLACES"
