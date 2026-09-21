"""The live transport must name its own number (PRD §26.1.2).

`WhatsAppBusinessProvider` posts to `{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages`,
and the template directory reads `{WHATSAPP_BUSINESS_ACCOUNT_ID}`. Both were once committed
defaults carrying the *production* identifiers, which was harmless only while every non-prod
environment ran the stub. The moment staging runs `meta`, a forgotten Doppler value stops
being a misconfiguration and becomes staging sending from the production number to real
customers' handsets — silently, because a valid-looking id needs no fallback.

So the identifiers have no defaults, and the live transport refuses to boot without them.
A missing value is now a deploy that fails, which is the only failure mode that cannot reach
a customer.
"""
import pytest
from pydantic import ValidationError

from main.app.config.settings import Settings
from main.appodus_utils.config.settings import Environment, OtpMode, WhatsAppProvider

_META_IDS = dict(
    WHATSAPP_PHONE_NUMBER_ID="111111111111111",
    WHATSAPP_BUSINESS_ACCOUNT_ID="222222222222222",
)


def _settings(**over):
    """Build Settings for a live-transport environment.

    Init kwargs outrank the env file, so this is independent of `.env.test`. Staging is the
    environment under test because it is the one that may run either transport — and the one
    the hazard above is actually about.
    """
    base = dict(
        ENVIRONMENT=Environment.STAGING,
        OTP_MODE=OtpMode.RANDOM,
        AUTHJWT_SECRET_KEY="a-strong-unique-key",
        WHATSAPP_PROVIDER=WhatsAppProvider.META,
        **_META_IDS,
    )
    base.update(over)
    return Settings(**base)


class TestWhatsAppIdentityPolicy:
    def test_no_committed_default_carries_a_real_identifier(self):
        """The regression this whole guard exists for: an unset id must be unset."""
        fields = Settings.model_fields
        assert fields["WHATSAPP_PHONE_NUMBER_ID"].default is None
        assert fields["WHATSAPP_BUSINESS_ACCOUNT_ID"].default is None

    def test_live_transport_accepts_explicit_identifiers(self):
        s = _settings()
        assert s.WHATSAPP_PHONE_NUMBER_ID == _META_IDS["WHATSAPP_PHONE_NUMBER_ID"]
        assert s.WHATSAPP_BUSINESS_ACCOUNT_ID == _META_IDS["WHATSAPP_BUSINESS_ACCOUNT_ID"]

    @pytest.mark.parametrize(
        "missing", ["WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID"]
    )
    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_live_transport_refuses_a_missing_identifier(self, missing, blank):
        with pytest.raises(ValidationError, match=missing):
            _settings(**{missing: blank})

    def test_the_stub_needs_no_identifiers(self):
        # The stub records to an in-process outbox and addresses nothing, so requiring
        # Meta ids there would block every local run and all of CI.
        s = _settings(
            WHATSAPP_PROVIDER=WhatsAppProvider.STUB,
            WHATSAPP_PHONE_NUMBER_ID=None,
            WHATSAPP_BUSINESS_ACCOUNT_ID=None,
        )
        assert s.WHATSAPP_PROVIDER == WhatsAppProvider.STUB
