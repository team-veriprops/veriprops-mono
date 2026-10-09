"""A deployed environment must be able to run its sweeps (D12 follow-up, Stage 6).

Every deployed environment is serverless, where the in-process scheduler cannot be trusted
to fire. The sweeps — message retries, scheduled broadcasts, the daily payout batch, SLA
breaches, commission clearance — run only when the Cloudflare Cron Worker calls
`POST /internal/sweeps/tick`, and that endpoint answers 404 until `SWEEP_TRIGGER_SECRET` is
set. A production or staging build without it would boot and look healthy while nothing
time-driven ever happened, so it refuses to boot instead.
"""
import pytest
from pydantic import ValidationError

from main.app.config.settings import Settings
from main.appodus_utils.config.settings import Environment, OtpMode, WhatsAppProvider
from test.unit.app.config.test_live_integration_policy import _LIVE


def _settings(env, **over):
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


def test_the_secret_is_a_credential_kept_out_of_committed_files():
    assert "SWEEP_TRIGGER_SECRET" in Settings.SECRET_ENV_KEYS


@pytest.mark.parametrize("env", [Environment.PRODUCTION, Environment.STAGING])
def test_a_deployed_environment_boots_with_the_secret(env):
    assert _settings(env).SWEEP_TRIGGER_SECRET == "a-strong-sweep-secret"


@pytest.mark.parametrize("env", [Environment.PRODUCTION, Environment.STAGING])
@pytest.mark.parametrize("blank", ["", "   ", "CHANGE_ME"])
def test_a_deployed_environment_refuses_to_boot_without_it(env, blank):
    with pytest.raises(ValidationError, match="SWEEP_TRIGGER_SECRET"):
        _settings(env, SWEEP_TRIGGER_SECRET=blank)


@pytest.mark.parametrize("env", [Environment.DEVELOPMENT, Environment.DEV_PERSONAL])
def test_other_environments_boot_without_it(env):
    # Local runs drive the same tick from the in-process scheduler, and the endpoint stays
    # disabled (404) until a secret is set.
    s = _settings(env, OTP_MODE=OtpMode.DETERMINISTIC, WHATSAPP_PROVIDER=WhatsAppProvider.STUB,
                  SWEEP_TRIGGER_SECRET="")
    assert s.SWEEP_TRIGGER_SECRET == ""
