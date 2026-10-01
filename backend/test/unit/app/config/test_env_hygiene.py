"""Env-file hygiene guards.

Committed `.env.{env}` files are **config-only**: every credential named in
`Settings.SECRET_ENV_KEYS` must be absent, empty, or the `CHANGE_ME` placeholder.
Real secret values are injected as process env vars by the secrets manager
(Doppler), which pydantic-settings gives precedence over env_file values.

These tests are the tripwire that keeps a real credential from ever being
committed again — they scan the backend and frontend env files with both a
key-based rule (SECRET_ENV_KEYS) and a provider-token pattern scan, and pin the
per-environment contracts (.env.test is inert/deterministic, .env.prod is
locked down).
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from main.app.config.settings import Settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER

# test/unit/app/config/ -> backend/ -> repo root
BACKEND_DIR = Path(__file__).resolve().parents[4]
REPO_ROOT = BACKEND_DIR.parent

# Committed, config-only env files (hygiene-enforced). .env.dev_personal is
# deliberately excluded — it's gitignored/per-developer, not committed.
BACKEND_ENV_FILES = [".env.example", ".env.test", ".env.dev", ".env.staging", ".env.prod"]
# .env.dev / .env.staging are deploy-time files (parsed by deploy.yml into
# --build-env/--env flags — Next.js never auto-loads custom env-file names).
FRONTEND_ENV_FILES = [".env", ".env.test", ".env.dev", ".env.staging", ".env.production"]

# Deterministic seed credentials for throwaway local/test databases. These are
# not secrets (they gate nothing outside a developer's own machine / the CI test
# DB) but they must stay pinned so the automation contract stays deterministic.
ALLOWED_SEED_CREDENTIALS: Dict[Tuple[str, str], str] = {
    (".env.test", "SUPER_ADMIN_PASSWORD"): "Admin123!test",
}

# Values that are always acceptable for a secret key in a committed env file.
# "mock_value" is the settings-module insecure sentinel for OAuth provider mocks.
INERT_SECRET_VALUES = {"", SECRET_PLACEHOLDER, "mock_value"}

# Provider-issued token shapes that must never appear anywhere in a committed
# env file — belt-and-braces on top of the key-based rule.
SECRET_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),          # AWS access key id
    re.compile(r"GOCSPX-"),                   # Google OAuth client secret
    re.compile(r"FLWSECK"),                   # Flutterwave secret/webhook key
    re.compile(r"\bsk_(test|live)_"),         # Paystack/Stripe secret key
    re.compile(r"\bpk_(test|live)_"),         # Paystack/Stripe publishable key
    re.compile(r"\btsk_"),                    # Termii secret key
    re.compile(r"\bAVNS_"),                   # Aiven service password
    re.compile(r"-----BEGIN"),                # PEM private key material
]

# Settings fields that are internal/derived and deliberately not settable via
# the documented .env.example template.
TEMPLATE_EXEMPT_FIELDS = {
    "BASE_DIR",                    # derived from the package location
    "SQLALCHEMY_DATABASE_URI",     # assembled from the DB_* parts
    "DB_MAIN_THREAD_CONTEXT_ID",   # internal session-context constant
    "TEST_OTP",                    # canonical deterministic OTP, fixed by contract
    # Pinned security invariants — identical in every environment by design
    # (__Host- cookie names must not be renamed; the JWT algorithm allowlist is
    # locked to HS256 against algorithm-confusion). Not per-env knobs.
    "AUTHJWT_TOKEN_LOCATION",
    "AUTHJWT_ACCESS_COOKIE_KEY",
    "AUTHJWT_REFRESH_COOKIE_KEY",
    "AUTHJWT_ACCESS_CSRF_COOKIE_KEY",
    "AUTHJWT_REFRESH_CSRF_COOKIE_KEY",
    "AUTHJWT_ALGORITHM",
    "AUTHJWT_DECODE_ALGORITHMS",
}


def _env_path(name: str, frontend: bool = False) -> Path:
    return (REPO_ROOT / "frontend" / name) if frontend else (BACKEND_DIR / name)


def _parse_env(path: Path) -> Dict[str, str]:
    """Parse KEY=value lines; strips inline ` # comment` tails and quotes."""
    values: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # dotenv treats a hash preceded by whitespace as a comment start
        value = re.split(r"\s+#", value, maxsplit=1)[0].strip().strip("'\"")
        values[key.strip()] = value
    return values


def _documented_keys(path: Path) -> set:
    """Keys documented in a template — both active `KEY=` and commented `# KEY=` lines."""
    keys = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#?\s*([A-Z][A-Z0-9_]*)=", raw.strip())
        if match:
            keys.add(match.group(1))
    return keys


def _all_env_paths() -> List[Path]:
    return [_env_path(n) for n in BACKEND_ENV_FILES] + [
        _env_path(n, frontend=True) for n in FRONTEND_ENV_FILES
    ]


class TestSecretKeyRegistry:
    def test_every_secret_key_is_a_settings_field(self):
        """Catches a typo'd SECRET_ENV_KEYS entry that would silently guard nothing."""
        unknown = Settings.SECRET_ENV_KEYS - set(Settings.model_fields)
        assert not unknown, f"SECRET_ENV_KEYS entries that are not Settings fields: {sorted(unknown)}"

    def test_no_next_public_key_is_classified_secret(self):
        """NEXT_PUBLIC_* values are inlined into the browser bundle — a secret there
        is a leak by construction."""
        leaked = {k for k in Settings.SECRET_ENV_KEYS if k.startswith("NEXT_PUBLIC_")}
        assert not leaked


class TestCommittedEnvFilesAreConfigOnly:
    @pytest.mark.parametrize("path", _all_env_paths(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
    def test_env_file_exists(self, path: Path):
        assert path.exists(), f"{path} is part of the committed env-file set but is missing"

    @pytest.mark.parametrize("name", BACKEND_ENV_FILES)
    def test_no_secret_values_for_secret_keys(self, name: str):
        values = _parse_env(_env_path(name))
        offenders = []
        for key in sorted(Settings.SECRET_ENV_KEYS):
            if key not in values:
                continue
            value = values[key]
            if value in INERT_SECRET_VALUES:
                continue
            if ALLOWED_SEED_CREDENTIALS.get((name, key)) == value:
                continue
            offenders.append(key)
        assert not offenders, (
            f"{name} carries real-looking values for secret keys {offenders}; "
            f"move them to Doppler and leave the key absent/empty/{SECRET_PLACEHOLDER}."
        )

    @pytest.mark.parametrize("name", BACKEND_ENV_FILES)
    def test_no_value_is_read_as_its_own_comment(self, name: str):
        """`KEY=    # note` is read by python-dotenv (what pydantic-settings loads with) as the
        value "# note", not as blank: a support phone printed into every message as comment
        text, and a secret that counts as configured. A blank value keeps its note on the line
        above instead."""
        from dotenv import dotenv_values

        read_as_comment = sorted(
            key for key, value in dotenv_values(_env_path(name)).items() if (value or "").startswith("#")
        )
        assert not read_as_comment, (
            f"{name}: {read_as_comment} load as their comment text; move the comment to its own line"
        )

    def test_frontend_backend_secret_key_is_inert(self):
        for name in FRONTEND_ENV_FILES:
            values = _parse_env(_env_path(name, frontend=True))
            value = values.get("BACKEND_SECRET_KEY", "")
            assert value in INERT_SECRET_VALUES, (
                f"frontend/{name}: BACKEND_SECRET_KEY must stay empty/{SECRET_PLACEHOLDER} "
                "in committed files (real value via Doppler / .env.dev_personal)."
            )

    @pytest.mark.parametrize("path", _all_env_paths(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
    def test_no_provider_token_patterns(self, path: Path):
        offenders = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in SECRET_VALUE_PATTERNS:
                if pattern.search(line):
                    offenders.append((line_no, pattern.pattern))
        assert not offenders, f"{path.name} contains provider-token-shaped values at {offenders}"


class TestTestEnvContract:
    """`.env.test` must be inert and deterministic — pytest and the QA automation
    stack depend on it never touching shared infrastructure or real providers."""

    @pytest.fixture(scope="class")
    def env(self) -> Dict[str, str]:
        return _parse_env(_env_path(".env.test"))

    def test_environment_and_otp(self, env):
        assert env["ENVIRONMENT"] == "test"
        assert env["OTP_MODE"] == "deterministic"

    def test_external_providers_are_pinned_to_their_stubs(self, env):
        """The automation-determinism contract: no automated run reaches Meta or a model.

        Both are also enforced at startup, but a committed file that disagreed with the
        validator would fail every test run with a boot error instead of saying why.
        """
        assert env["WHATSAPP_PROVIDER"] == "stub"
        assert env["INTENT_PROVIDER"] == "stub"

    def test_no_background_or_outbound_side_effects(self, env):
        assert env["SCHEDULER_ENABLED"] == "false"
        assert env["ENABLE_OUT_MESSAGING"] == "false"

    def test_local_isolated_database(self, env):
        assert env["DB_SERVER"] == "localhost"
        assert env["DB_NAME"] == "veriprops_test"

    def test_stub_modes_on(self, env):
        assert env["PAYMENT_STUB_MODE"] == "true"
        assert env["DOCUMENT_STORAGE_STUB_MODE"] == "true"
        assert env["REPORT_PDF_STUB_MODE"] == "true"

    def test_mailpit_smtp(self, env):
        # The IPv4 loopback, not `localhost`: on Windows `localhost` tries ::1 first, which
        # stalls every host-run send to Mailpit (backend/CLAUDE.md, "Serverless-aware DB engine").
        assert env["SMTP_HOST"] == "127.0.0.1"
        assert env["SMTP_PORT"] == "1025"


class TestProdEnvContract:
    """`.env.prod` is committed config-only; these are the boot-safety knobs that
    must never drift (secrets themselves arrive via Doppler-injected env vars)."""

    @pytest.fixture(scope="class")
    def env(self) -> Dict[str, str]:
        return _parse_env(_env_path(".env.prod"))

    def test_environment_and_otp(self, env):
        assert env["ENVIRONMENT"] == "prod"
        assert env["OTP_MODE"] == "random"

    def test_hardening_flags(self, env):
        assert env["SHOW_API"] == "false"
        assert env["DISABLE_RATE_LIMITING"] == "false"
        assert env["DB_ENABLE_LOGS"] == "false"

    def test_stub_modes_off(self, env):
        assert env["PAYMENT_STUB_MODE"] == "false"
        assert env["DOCUMENT_STORAGE_STUB_MODE"] == "false"
        assert env["REPORT_PDF_STUB_MODE"] == "false"
        # The stub transport must never serve a real customer (D43); the intent stub is
        # a keyword table, which would quietly halve the bot's free-text coverage.
        assert env["WHATSAPP_PROVIDER"] == "meta"
        assert env["INTENT_PROVIDER"] != "stub"


class TestStagingEnvContract:
    """`.env.staging` is the human-QA environment, and its value comes from being like
    prod. Where it deliberately differs (Meta's test number rather than the official one),
    the difference is in Doppler, not here — so these pins are what stops staging quietly
    drifting back to stubs and leaving the live path to be discovered in production."""

    @pytest.fixture(scope="class")
    def env(self) -> Dict[str, str]:
        return _parse_env(_env_path(".env.staging"))

    def test_environment_and_otp(self, env):
        assert env["ENVIRONMENT"] == "staging"
        assert env["OTP_MODE"] == "random"

    def test_live_providers_mirror_prod(self, env):
        prod = _parse_env(_env_path(".env.prod"))
        assert env["WHATSAPP_PROVIDER"] == "meta"
        assert env["INTENT_PROVIDER"] == prod["INTENT_PROVIDER"]
        # A different model is a different bot; staging would stop predicting prod.
        assert env["INTENT_MODEL"] == prod["INTENT_MODEL"]

    def test_meta_identifiers_are_not_committed_here(self, env):
        """Staging must take its number from Doppler `stg`.

        A value in this file would be reviewable, which is exactly the risk: the number is
        what the channel *is*, and the wrong one sends QA traffic to real customers.
        """
        assert "WHATSAPP_PHONE_NUMBER_ID" not in env
        assert "WHATSAPP_BUSINESS_ACCOUNT_ID" not in env


class TestTemplateDriftGuard:
    def test_every_settable_field_is_documented_in_env_example(self):
        """`.env.example` is the discoverability surface for every knob — a new
        Settings field must land there (active or commented) in the same PR."""
        documented = _documented_keys(_env_path(".env.example"))
        settable = set(Settings.model_fields) - TEMPLATE_EXEMPT_FIELDS
        missing = {f for f in settable if f.upper() not in documented}
        assert not missing, (
            f".env.example is missing keys for Settings fields: {sorted(missing)}; "
            "add them (commented is fine) or add to TEMPLATE_EXEMPT_FIELDS with a reason."
        )


class TestNoTrackedPrivateKeys:
    """Service-account keys arrive as base64 JSON from Doppler (`*_JSON_B64` settings); a local
    key file is gitignored and never shipped. A tracked file holding private-key material is a
    leaked credential the moment it is pushed, whatever its name or extension."""

    def test_no_tracked_file_holds_private_key_material(self):
        import shutil
        import subprocess

        if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
            pytest.skip("not a git checkout")
        # `-e`: the pattern starts with dashes, which git would otherwise parse as an option.
        found = subprocess.run(
            ["git", "grep", "-l", "-E", "-e", r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        # git grep exits 1 for "no match"; anything else means the scan itself failed.
        assert found.returncode in (0, 1), f"git grep failed: {found.stderr}"
        offenders = found.stdout.split()
        assert not offenders, (
            f"tracked files hold private-key material: {offenders}; untrack them "
            "(`git rm --cached`), rotate the key, and load it from Doppler instead."
        )
