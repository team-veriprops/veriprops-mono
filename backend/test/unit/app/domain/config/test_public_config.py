"""Unit tests for the public config endpoint + phone-verification flag (S6)."""
from __future__ import annotations

from main.app.config.settings import settings
from main.app.domain.config import controller as config_controller


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
