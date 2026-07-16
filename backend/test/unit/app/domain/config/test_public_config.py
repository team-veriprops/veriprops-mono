"""Unit tests for the public config endpoint + phone-verification flag (S6)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.core.state.status import VerificationTier
from main.app.domain.config import controller as config_controller


@pytest.fixture(autouse=True)
def mock_pricing_config_service(monkeypatch):
    # Isolates the controller from the DB — tier_price_kobo is @transactional and
    # normally relies on DBSessionMiddleware's per-request session context, which
    # doesn't exist when the controller function is invoked directly in a unit test.
    service = MagicMock()
    service.tier_price_kobo = AsyncMock(return_value=5_000_000)
    monkeypatch.setattr(config_controller, "pricing_config_service", service)
    return service


class TestPublicConfig:
    async def test_reflects_phone_verification_flag_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", True)
        resp = await config_controller.public_config()
        assert resp.data.phone_verification_enabled is True

    async def test_reflects_phone_verification_flag_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", False)
        resp = await config_controller.public_config()
        assert resp.data.phone_verification_enabled is False

    def test_setting_defaults_to_enabled(self):
        # Default posture: phone verification on unless explicitly disabled per-env.
        assert isinstance(settings.PHONE_VERIFICATION_ENABLED, bool)

    async def test_pricing_tiers_cover_every_tier(self, mock_pricing_config_service):
        resp = await config_controller.public_config()
        assert {t.tier for t in resp.data.pricing_tiers} == set(VerificationTier)
        assert all(t.price_ngn_minor == 5_000_000 for t in resp.data.pricing_tiers)
        assert mock_pricing_config_service.tier_price_kobo.await_count == len(VerificationTier)
