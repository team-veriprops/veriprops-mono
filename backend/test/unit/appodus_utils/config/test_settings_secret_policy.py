"""Prod/staging fail-fast secret policy (C1/C2).

The whole point is that a prod/staging build refuses to boot with a placeholder or the
historically-committed default JWT signing key, so a mislabeled env file can never sign
tokens with a guessable secret.
"""
import pytest
from pydantic import ValidationError

from main.appodus_utils.config.settings import (
    AppodusBaseSettings,
    Environment,
    SECRET_PLACEHOLDER,
)

_LEAKED_DEFAULT = "d344auth_jwt_s3cr3t-635678$%#agst634"


def _settings(**over):
    base = dict(
        ENVIRONMENT=Environment.PRODUCTION,
        AUTHJWT_SECRET_KEY="a-strong-unique-key",
        OTP_MODE="random",
        # Prod also pins the live WhatsApp transport (D43); without it the settings
        # object fails on that contract instead of the one under test.
        WHATSAPP_PROVIDER="meta",
    )
    base.update(over)
    return AppodusBaseSettings(**base)


class TestProdSecretPolicy:
    def test_placeholder_jwt_key_refuses_to_boot(self):
        with pytest.raises(ValidationError):
            _settings(AUTHJWT_SECRET_KEY=SECRET_PLACEHOLDER)

    def test_committed_leaked_default_refuses_to_boot(self):
        with pytest.raises(ValidationError):
            _settings(AUTHJWT_SECRET_KEY=_LEAKED_DEFAULT)

    def test_staging_is_treated_like_prod(self):
        with pytest.raises(ValidationError):
            _settings(ENVIRONMENT=Environment.STAGING, AUTHJWT_SECRET_KEY=SECRET_PLACEHOLDER)

    def test_valid_prod_settings_boot(self):
        s = _settings()
        assert s.ENVIRONMENT == Environment.PRODUCTION

    def test_non_prod_allows_placeholder(self):
        # dev_personal/dev/test must still run with placeholder secrets.
        s = AppodusBaseSettings(
            ENVIRONMENT=Environment.DEV_PERSONAL, AUTHJWT_SECRET_KEY=SECRET_PLACEHOLDER
        )
        assert s.AUTHJWT_SECRET_KEY == SECRET_PLACEHOLDER


class TestAlgorithmPinned:
    def test_algorithm_and_decode_allowlist_are_hs256(self):
        s = AppodusBaseSettings(ENVIRONMENT=Environment.DEV_PERSONAL)
        assert s.AUTHJWT_ALGORITHM == "HS256"
        assert s.AUTHJWT_DECODE_ALGORITHMS == ["HS256"]
