"""WhatsApp transport determinism contract (PRD §7, D43).

Mirrors the OTP_MODE contract: CI and e2e must never reach Meta, and production must
never run on the stub. Both are startup failures rather than runtime surprises.
"""
import pytest
from pydantic import ValidationError

from main.appodus_utils.config.settings import (
    AppodusBaseSettings,
    Environment,
    OtpMode,
    WhatsAppProvider,
)


def _settings(**over):
    base = dict(
        ENVIRONMENT=Environment.DEVELOPMENT,
        AUTHJWT_SECRET_KEY="a-strong-unique-key",
        OTP_MODE=OtpMode.DETERMINISTIC,
    )
    base.update(over)
    return AppodusBaseSettings(**base)


class TestWhatsAppProviderPolicy:
    def test_defaults_to_the_stub(self):
        # Nothing reaches Meta unless an environment opts in explicitly.
        assert _settings().WHATSAPP_PROVIDER == WhatsAppProvider.STUB

    def test_test_env_refuses_the_live_transport(self):
        with pytest.raises(ValidationError):
            _settings(
                ENVIRONMENT=Environment.TEST,
                OTP_MODE=OtpMode.DETERMINISTIC,
                WHATSAPP_PROVIDER=WhatsAppProvider.META,
            )

    def test_production_refuses_the_stub(self):
        with pytest.raises(ValidationError):
            _settings(
                ENVIRONMENT=Environment.PRODUCTION,
                OTP_MODE=OtpMode.RANDOM,
                WHATSAPP_PROVIDER=WhatsAppProvider.STUB,
            )

    def test_production_accepts_the_live_transport(self):
        s = _settings(
            ENVIRONMENT=Environment.PRODUCTION,
            OTP_MODE=OtpMode.RANDOM,
            WHATSAPP_PROVIDER=WhatsAppProvider.META,
        )
        assert s.WHATSAPP_PROVIDER == WhatsAppProvider.META

    def test_staging_may_run_either_transport(self):
        # Staging is the human-QA environment: it exercises the live path once Meta
        # assets exist, but must still boot on the stub before then.
        for provider in (WhatsAppProvider.STUB, WhatsAppProvider.META):
            s = _settings(
                ENVIRONMENT=Environment.STAGING,
                OTP_MODE=OtpMode.RANDOM,
                WHATSAPP_PROVIDER=provider,
            )
            assert s.WHATSAPP_PROVIDER == provider
