"""Guards for the settings-externalization work: the operational knobs that were
in-code constants now resolve through Settings / OtpMode / the system_config store,
and formerly-shadowed settings are actually the ones read at runtime.
"""
import pytest

from main.app.config.settings import settings
from main.app.domain.system_config.models import CONFIG_DEFAULTS, CONFIG_DESCRIPTIONS, ConfigKey
from main.appodus_utils.config.settings import OtpMode


class TestNewSettingsDefaults:
    def test_otp_delivery_knobs_have_documented_defaults(self):
        assert settings.OTP_CODE_TTL_SECONDS == 60 * 10
        assert settings.OTP_MAX_RESENDS == 3
        assert settings.OTP_RESEND_LOCKOUT_SECONDS == 60 * 30
        assert settings.OTP_MAX_FAILURES == 5
        assert settings.OTP_VERIFIED_MARKER_TTL_SECONDS == 60 * 30

    def test_oauth_and_lifetime_knobs_present(self):
        assert settings.OAUTH_STATE_TTL_SECONDS == 60 * 10
        assert settings.OAUTH_JWKS_CACHE_SECONDS == 60 * 5
        assert settings.OAUTH_CLIENT_SECRET_JWT_TTL_SECONDS == 60 * 5
        assert settings.SIGNUP_DRAFT_TTL_DAYS == 7
        assert settings.AGENT_APPLICATION_DRAFT_TTL_DAYS == 30
        assert settings.VERIFICATION_ABANDONMENT_AGE_HOURS == 24
        assert settings.IDEMPOTENCY_KEY_TTL_HOURS == 24

    def test_sse_and_ui_limit_knobs_present(self):
        assert settings.SSE_HEARTBEAT_SECONDS == 25
        assert settings.SSE_QUEUE_MAXSIZE == 100
        assert settings.CHAT_MESSAGE_MAX_LENGTH == 2000
        assert settings.PASSWORD_MIN_LENGTH == 8

    def test_committed_defaults_are_not_personal_or_leaked(self):
        # Personal ngrok/gmail/phone were removed from committed defaults (Part C).
        assert "gmail.com" not in settings.BRAND_SUPPORT_EMAIL
        assert settings.BRAND_SUPPORT_EMAIL == "support@veriprops.ng"
        assert "192.168." not in (settings.ALLOWED_ORIGINS or "")


class TestOtpModeEnum:
    def test_otp_mode_is_enum(self):
        assert isinstance(settings.OTP_MODE, OtpMode)
        # Test env must be deterministic (enforced by _enforce_otp_mode_policy).
        assert settings.OTP_MODE == OtpMode.DETERMINISTIC


class TestShadowedConstantsRemoved:
    """The former module-level constants that silently shadowed a setting are gone;
    the services now read the setting instead."""

    def test_otp_service_ttl_derives_from_setting(self):
        from main.app.domain.user.auth import otp_service

        assert int(otp_service.OTP_TTL.total_seconds()) == settings.OTP_CODE_TTL_SECONDS
        assert otp_service.MAX_RESENDS == settings.OTP_MAX_RESENDS
        assert otp_service.MAX_FAILURES == settings.OTP_MAX_FAILURES
        # The delivery-message validity label is derived from the TTL, never a literal.
        assert otp_service._validity_label() == "10 minutes"

    def test_admin_invitation_ttl_constant_gone(self):
        from main.app.domain.user.admin_invitation import service as invite_service

        assert not hasattr(invite_service, "INVITE_TTL_HOURS")

    def test_auth_lockout_dead_constants_gone(self):
        from main.app.domain.user.auth import service as auth_service

        assert not hasattr(auth_service, "LOCKOUT_THRESHOLD")
        assert not hasattr(auth_service, "LOCKOUT_MINUTES")


class TestNewConfigKeys:
    @pytest.mark.parametrize(
        "key",
        [
            ConfigKey.SLA_AT_RISK_DAYS,
            ConfigKey.PAYOUT_SLA_BUSINESS_DAYS,
            ConfigKey.DISPUTE_MIN_DESCRIPTION_CHARS,
            ConfigKey.SHARE_LINK_DEFAULT_EXPIRY_DAYS,
            ConfigKey.ANALYTICS_TREND_MONTHS,
        ],
    )
    def test_new_business_knobs_have_seed_defaults_and_descriptions(self, key):
        assert key in CONFIG_DEFAULTS
        assert isinstance(CONFIG_DEFAULTS[key], int)
        assert key in CONFIG_DESCRIPTIONS
