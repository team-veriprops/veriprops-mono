"""Production refuses to boot on a stub, or on a live integration it has no keys for.

Until now production ran the KYC and geocoding stubs: the KYC stub approves any BVN, so an
impostor could become a verified agent, and address search offered three fixture addresses.
Each stub exists for tests and local work; nothing but a setting kept it out of production.

So in production, and only there (staging is free to run either way while its keys are
arranged), the settings must select every live integration and carry its credentials:
payments, document storage, Dojah KYC against its production host, and Google Places. A
missing piece is a deploy that fails — with every missing piece named at once — which is the
only failure mode that cannot reach a customer.
"""
import pytest
from pydantic import ValidationError

from main.app.config.settings import PaymentMethod, Settings
from main.appodus_utils.config.settings import Environment, OtpMode, WhatsAppProvider

_LIVE = dict(
    PAYMENT_STUB_MODE=False,
    ACTIVE_PAYMENT_METHOD=PaymentMethod.FLUTTERWAVE,
    FLUTTERWAVE_SECRET_KEY="FLWSECK-live",
    FLUTTERWAVE_WEBHOOK_SECRET="flw-hash",
    PAYSTACK_SECRET_KEY="sk_live_x",
    DOCUMENT_STORAGE_STUB_MODE=False,
    KYC_PROVIDER="DOJAH",
    DOJAH_APP_ID="app-live",
    DOJAH_PRIVATE_KEY="prod_sk_x",
    DOJAH_BASE_URL="https://api.dojah.io",
    GEOCODING_PROVIDER="GOOGLE_PLACES",
    GOOGLE_PLACES_API_KEY="AIza-live",
    AWS_ACCESS_KEY="AKIA-live",
    AWS_SECRET_ACCESS_KEY="aws-secret-live",
)


def _settings(env=Environment.PRODUCTION, **over):
    base = dict(
        ENVIRONMENT=env,
        OTP_MODE=OtpMode.RANDOM,
        AUTHJWT_SECRET_KEY="a-strong-unique-key",
        WHATSAPP_PROVIDER=WhatsAppProvider.META,
        WHATSAPP_PHONE_NUMBER_ID="111111111111111",
        WHATSAPP_BUSINESS_ACCOUNT_ID="222222222222222",
        SWEEP_TRIGGER_SECRET="a-strong-sweep-secret",
        **_LIVE,
    )
    base.update(over)
    return Settings(**base)


class TestProductionRunsLive:
    def test_production_boots_with_every_integration_live(self):
        assert _settings().KYC_PROVIDER == "DOJAH"

    @pytest.mark.parametrize("override, named", [
        ({"PAYMENT_STUB_MODE": True}, "PAYMENT_STUB_MODE"),
        ({"DOCUMENT_STORAGE_STUB_MODE": True}, "DOCUMENT_STORAGE_STUB_MODE"),
        ({"KYC_PROVIDER": "STUB"}, "KYC_PROVIDER"),
        ({"GEOCODING_PROVIDER": "STUB"}, "GEOCODING_PROVIDER"),
    ])
    def test_a_stub_is_refused(self, override, named):
        with pytest.raises(ValidationError, match=named):
            _settings(**override)

    @pytest.mark.parametrize("key", ["DOJAH_APP_ID", "DOJAH_PRIVATE_KEY", "GOOGLE_PLACES_API_KEY",
                                     "FLUTTERWAVE_SECRET_KEY", "FLUTTERWAVE_WEBHOOK_SECRET",
                                     "AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"])
    @pytest.mark.parametrize("blank", ["", "CHANGE_ME"])
    def test_a_live_integration_without_its_key_is_refused(self, key, blank):
        with pytest.raises(ValidationError, match=key):
            _settings(**{key: blank})

    def test_the_paystack_key_is_required_when_paystack_collects(self):
        with pytest.raises(ValidationError, match="PAYSTACK_SECRET_KEY"):
            _settings(ACTIVE_PAYMENT_METHOD=PaymentMethod.PAYSTACK, PAYSTACK_SECRET_KEY="")

    def test_dojahs_sandbox_is_refused_in_production(self):
        # Sandbox answers are mock data: a sandbox "match" is no evidence of anyone's identity.
        with pytest.raises(ValidationError, match="DOJAH_BASE_URL"):
            _settings(DOJAH_BASE_URL="https://sandbox.dojah.io")

    def test_every_problem_is_named_at_once(self):
        with pytest.raises(ValidationError) as exc:
            _settings(KYC_PROVIDER="STUB", GEOCODING_PROVIDER="STUB", PAYMENT_STUB_MODE=True)
        message = str(exc.value)
        assert all(name in message for name in ("KYC_PROVIDER", "GEOCODING_PROVIDER", "PAYMENT_STUB_MODE"))


class TestOtherEnvironmentsAreUnconstrained:
    def test_staging_may_run_stubs_while_its_keys_are_arranged(self):
        s = _settings(env=Environment.STAGING, KYC_PROVIDER="STUB", GEOCODING_PROVIDER="STUB",
                      DOJAH_PRIVATE_KEY="", GOOGLE_PLACES_API_KEY="", DOJAH_BASE_URL="https://sandbox.dojah.io")
        assert s.KYC_PROVIDER == "STUB"
