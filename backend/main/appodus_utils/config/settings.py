import base64
import enum
import json
import os
import re
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, Optional, Any, Dict, List
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from pydantic import Field, field_validator, ValidationInfo, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_absolute_path(path: str):
    directory = os.getcwd()
    test = 'test'
    main = 'main'
    appodus_utils = 'appodus_utils'
    if test in directory:
        directory = directory.split(sep=test)[0]
    if main in directory:
        directory = directory.split(sep=main)[0]
    if appodus_utils in directory:
        directory = directory.split(sep=appodus_utils)[0]
    directory = os.path.join(directory, path)

    return directory

class FileStorage(str, enum.Enum):
    R2 = "R2"
    S3 = "S3"
    STUB = "STUB"  # deterministic local provider for tests/dev (no external calls)

class SupportedDB(str, enum.Enum):
    MYSQL = 'MYSQL'
    MSSQL = 'MSSQL'
    POSTGRES = 'POSTGRES'
    ORACLE = 'ORACLE'

class Environment(str, enum.Enum):
    PRODUCTION = "prod"
    STAGING = "staging"
    TEST = "test"
    DEVELOPMENT = "dev"
    DEV_PERSONAL = "dev_personal"

class TemplatingEngine(str, enum.Enum):
    JINJA2 = "jinja2"


class OtpMode(str, enum.Enum):
    """OTP determinism contract. ``deterministic`` always returns ``TEST_OTP`` (required
    in test, allowed in dev/dev_personal/staging); ``random`` generates a CSPRNG code (required
    in production). Enforced by ``_enforce_otp_mode_policy``."""

    DETERMINISTIC = "deterministic"
    RANDOM = "random"


# Secrets left at this placeholder must be supplied via the environment before a
# prod/staging boot. The startup validator (`_enforce_prod_secret_policy`) refuses
# to start a prod/staging build whose security-critical secrets are still unset or
# left at a placeholder — this is what keeps a mislabeled env file from silently
# shipping a known/default signing key.
SECRET_PLACEHOLDER = "CHANGE_ME"

# Values never acceptable for a security-critical secret in prod/staging: the shared
# placeholders plus the historically-committed (now public) JWT signing default.
_INSECURE_SECRET_VALUES = {
    SECRET_PLACEHOLDER,
    "mock_value",
    "",
    "d344auth_jwt_s3cr3t-635678$%#agst634",
}

# Settings fields that hold credentials. Single source of truth for env hygiene:
# committed .env.{env} files must never carry a real value for any of these keys —
# real values are injected as process env vars by the secrets manager (Doppler),
# which pydantic-settings gives precedence over env_file values. The app-level
# Settings class extends this set with its own credential fields; the guard test
# (test/unit/app/config/test_env_hygiene.py) enforces the contract on every
# committed env file (backend and frontend).
BASE_SECRET_ENV_KEYS: frozenset = frozenset({
    "AUTHJWT_SECRET_KEY",
    "DB_PASSWORD",
    "SMTP_PASSWORD",
    "GOOGLE_CLIENT_SECRET",
    "FACEBOOK_APP_SECRET",
    "APPLE_PRIVATE_KEY",
})

# The full settings snapshot (used by utils_settings to reconstruct the object) is
# kept off `os.environ` so the aggregated secret blob is not exposed via the process
# environment / `/proc/<pid>/environ` / subprocess inheritance. Read it via
# `get_full_settings_json()` rather than an env var.
_full_settings_json: Optional[str] = None


def get_full_settings_json() -> Optional[str]:
    """Return the JSON snapshot produced by the most recent `set_env_vars()` call.

    Consumers that previously read the `APPODUS_SETTINGS` environment variable should
    call this instead — the snapshot is held in-process, not in `os.environ`.
    """
    return _full_settings_json


class AppodusBaseSettings(BaseSettings):
    # Credential field names for this class; subclasses extend (see Settings).
    SECRET_ENV_KEYS: ClassVar[frozenset] = BASE_SECRET_ENV_KEYS

    # Brand identity — the real values are supplied per-env via .env.{env}. Committed
    # defaults are neutral placeholders, never personal contact details.
    BRAND: str = "appodus"
    BRAND_SUPPORT_EMAIL: str = "support@veriprops.ng"
    BRAND_SUPPORT_PHONE: str = ""

    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    ENABLE_OUT_MESSAGING: bool = False
    BASE_DIR: str = str(Path(__file__).parent.parent) # Used for accessing local files, e.g message templates

    APP_DOMAIN: str = "http://localhost:8000"
    SHOW_API: bool = True

    # Enable / Disable Services
    DISABLE_RATE_LIMITING: bool = False

    # LOGGING
    LOG_LEVEL: Optional[str] = 'DEBUG'
    LOGGER_FILE: Optional[str] = 'logs.txt'
    LOGGER_FILE_PATH: Optional[str] = '/tmp/logs'

    # ACTIVES
    ACTIVE_TEMPLATING_ENGINE: TemplatingEngine = TemplatingEngine.JINJA2

    # AUTH SESSION
    AUTH_LOCKOUT_THRESHOLD: int = 7
    AUTH_LOCKOUT_MINUTES: int = 15
    # Minimum length enforced by the server-side password-strength baseline.
    PASSWORD_MIN_LENGTH: int = 8

    # TOKEN
    ACCESS_TOKEN_TTL_SECONDS: int = 60 * 15  # 15 mins
    REFRESH_TOKEN_TTL_SECONDS: int = 60 * 60 * 24 * 30  # 30 days
    PASSWORD_RESET_TTL_SECONDS: int = 60 * 60  # 1 hour

    OTP_TOKEN_EXPIRE_SECONDS: Optional[int] = 60 * 5 # 5 mins
    EMAIL_OTP_TOKEN_EXPIRE_SECONDS: Optional[int] = 60 * 30 # 30 mins
    CACHE_DATA_EXPIRES_SECONDS: Optional[int] = 60 * 60 * 24 * 8 # Redis Default

    # OTP delivery & verification knobs (OtpService). The code TTL is the window a
    # sent code stays valid; resend/failure caps throttle abuse; the verified marker
    # lets a multi-step signup wizard confirm the OTP step without re-verifying.
    OTP_CODE_TTL_SECONDS: int = 60 * 10                 # 10 mins — sent-code validity
    OTP_MAX_RESENDS: int = 3                            # resends allowed within the lockout window
    OTP_RESEND_LOCKOUT_SECONDS: int = 60 * 30          # 30 mins — resend-count window
    OTP_MAX_FAILURES: int = 5                           # invalid attempts before a new code is required
    OTP_VERIFIED_MARKER_TTL_SECONDS: int = 60 * 30     # 30 mins — post-verify "completed" marker

    # OAuth provider caches / short-lived tokens (login popup flow).
    OAUTH_STATE_TTL_SECONDS: int = 60 * 10             # anti-CSRF state validity
    OAUTH_JWKS_CACHE_SECONDS: int = 60 * 5             # provider JWKS cache lifetime
    OAUTH_CLIENT_SECRET_JWT_TTL_SECONDS: int = 60 * 5  # Apple client-secret JWT exp

    # WEBHOOK
    WEBHOOK_PATH: Optional[str] = "/webhooks"

    # AUTH
    AUTH_URL_PATH: str ="/auth"
    # SOCIAL LOGIN
    SOCIAL_LOGIN_CALLBACK_PATH: Optional[str] = "/oauth"
    SOCIAL_LOGIN_SUCCESS_PATH: Optional[str] = "/auth/oauth/redirect"
    # GOOGLE
    GOOGLE_AUTH_BASE_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_CLIENT_ID: Optional[str] = "mock_value"
    GOOGLE_CLIENT_SECRET: Optional[str] = "mock_value"
    # FACEBOOK
    FACEBOOK_AUTH_BASE_URL: str = "https://www.facebook.com/v22.0/dialog/oauth"
    FACEBOOK_APP_ID: Optional[str] = "mock_value"
    FACEBOOK_APP_SECRET: Optional[str] = "mock_value"
    # APPLE
    APPLE_AUTH_BASE_URL: str = "https://appleid.apple.com/auth/authorize"
    APPLE_TEAM_ID: Optional[str] = "mock_value"
    APPLE_CLIENT_ID: Optional[str] = "mock_value"
    APPLE_KEY_ID: Optional[str] = "mock_value"
    APPLE_PRIVATE_KEY: Optional[str] = "mock_value"

    # AUTHJWT
    # Signing key for session JWTs. Symmetric (HS256), so the key IS the trust anchor:
    # anyone who knows it can forge an admin session. Never commit a real value — set
    # AUTHJWT_SECRET_KEY in the git-ignored .env.{env}. Prod/staging refuse to boot with
    # the placeholder/default (see `_enforce_prod_secret_policy`).
    AUTHJWT_SECRET_KEY: str = SECRET_PLACEHOLDER
    # Configure application to store and get JWT from cookies
    AUTHJWT_TOKEN_LOCATION: List[str] = Field(default_factory=lambda: ["cookies"])
    # Only allow JWT cookies to be sent over https
    # Note: access/refresh cookies use the `__Host-` prefix, which REQUIRES the Secure
    # attribute — so AUTHJWT_COOKIE_SECURE must stay `true` even locally, or the browser
    # silently drops the cookie and login never persists. Chrome treats http://localhost
    # as a secure context and accepts Secure cookies there, so plain http works for dev;
    # do not rename the cookie keys.
    AUTHJWT_COOKIE_SECURE: bool = True
    # Enable csrf double submit protection. default is True
    AUTHJWT_COOKIE_CSRF_PROTECT: bool = True
    # Change to 'lax' in production to make your website more secure from CSRF Attacks, default is None
    AUTHJWT_COOKIE_SAMESITE: str = 'lax'
    AUTHJWT_ACCESS_COOKIE_KEY: str = '__Host-access_token'
    AUTHJWT_REFRESH_COOKIE_KEY: str = '__Host-refresh_token'
    AUTHJWT_ACCESS_CSRF_COOKIE_KEY: str = '__Host-access_csrf_token'
    AUTHJWT_REFRESH_CSRF_COOKIE_KEY: str = '__Host-refresh_csrf_token'
    # Pin the signing + accepted-decode algorithm explicitly so no algorithm-confusion
    # is possible. HS256 is symmetric; keep the allowlist to the single algorithm.
    AUTHJWT_ALGORITHM: str = "HS256"
    AUTHJWT_DECODE_ALGORITHMS: List[str] = Field(default_factory=lambda: ["HS256"])

    # MESSAGING
    EMAIL_FROM_ADDRESS: Optional[str] = "noreply@example.com"
    EMAIL_FROM_NAME: str = "veriprops"
    SMS_SENDER_ID: Optional[str] = "veriprops"
    SMS_TTL: int = 25000

    MESSAGING_HEADERS: Dict[str, str] = {}
    MESSAGING_PRIORITY: int = 2
    MESSAGING_SANDBOX_MODE: bool = False
    MESSAGING_CATEGORIES: List[str] = []
    MESSAGING_RPS_LIMIT: int = 20
    MESSAGING_BULK_CONCURRENCY: int = 10
    # Backoff ladder for re-dispatching failed outbound messages; the retry
    # threshold is the list length (a message fails permanently after that many
    # retries, or earlier if its expires_at horizon would be crossed).
    # Env override uses JSON list syntax: MESSAGING_RETRY_INTERVALS_SECONDS=[5,5,5]
    MESSAGING_RETRY_INTERVALS_SECONDS: List[int] = [60, 300, 900]

    # SMTP (Mailpit in dev/test — auto-selected when ENVIRONMENT is not prod/staging)
    SMTP_HOST: Optional[str] = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = False
    # Bounds the SMTP socket. An SMTP host that accepts but blackholes the connection
    # (a stopped Mailpit container behind a port proxy) would otherwise pin the sending
    # worker thread forever and hang the request that triggered the mail. Socket errors
    # are not retried per-attempt (only httpx ones are), so a dead host costs exactly one
    # timeout inline and the message-level retry ladder carries the send from there —
    # keep this comfortably below the caller's HTTP timeout, yet far enough above normal
    # latency that a busy server never trips it.
    SMTP_TIMEOUT_SECONDS: int = 15

    # TEST CONFIG — canonical test OTP returned when OTP_MODE=deterministic
    TEST_OTP: int = 654123

    # OTP determinism contract (see OtpMode).
    OTP_MODE: OtpMode = OtpMode.DETERMINISTIC

    @model_validator(mode="after")
    def _enforce_otp_mode_policy(self) -> "AppodusBaseSettings":
        env = self.ENVIRONMENT
        mode = self.OTP_MODE
        if env == Environment.TEST and mode != OtpMode.DETERMINISTIC:
            raise ValueError(
                f"ENVIRONMENT=test requires OTP_MODE={OtpMode.DETERMINISTIC.value}, got '{mode.value}'. "
                f"Set OTP_MODE={OtpMode.DETERMINISTIC.value} in .env.test."
            )
        if env == Environment.PRODUCTION and mode != OtpMode.RANDOM:
            raise ValueError(
                f"ENVIRONMENT=prod requires OTP_MODE={OtpMode.RANDOM.value}, got '{mode.value}'. "
                "Deterministic OTP is forbidden in production."
            )
        return self

    @model_validator(mode="after")
    def _enforce_prod_secret_policy(self) -> "AppodusBaseSettings":
        """Fail fast if a prod/staging build is missing a security-critical secret or
        has an unsafe auth flag. This is the backstop for a mislabeled env file: even
        if `ENVIRONMENT` is set correctly but the JWT key was left at its placeholder
        (or the historically-leaked default), the app refuses to start rather than
        signing tokens with a guessable key.
        """
        if self.ENVIRONMENT not in (Environment.PRODUCTION, Environment.STAGING):
            return self

        env_name = self.ENVIRONMENT.value

        if (self.AUTHJWT_SECRET_KEY or "").strip() in _INSECURE_SECRET_VALUES:
            raise ValueError(
                f"AUTHJWT_SECRET_KEY must be a strong, unique secret in '{env_name}'. "
                "Refusing to start with a placeholder or the committed default key. "
                "Set AUTHJWT_SECRET_KEY in the environment."
            )

        return self

    # REDIS
    REDIS_ENABLED: Optional[bool] = False
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: Optional[str] = '0'
    REDIS_THREAD_SLEEP_TIME: Optional[float] = 0.01

    # DB
    ACTIVE_DB: Optional[SupportedDB] = SupportedDB.POSTGRES
    DB_SCHEME: Optional[str] = None
    DB_SERVER: Optional[str] = "sqlite:///"
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_PORT: Optional[str] = None
    DB_NAME: Optional[str] = None
    DB_ADDITIONAL_CONFIG: Optional[str] = None
    SQLALCHEMY_DATABASE_URI: Optional[Any] = None
    # SQL echo logs bound parameter values — keep off by default so PII/secrets in
    # query params are not written to logs. Enable explicitly per-env when debugging.
    DB_ENABLE_LOGS: Optional[bool] = False
    DB_ENABLE_LOG_POOL: Optional[bool] = True
    DB_MAIN_THREAD_CONTEXT_ID: int = 12345
    DEPLOYMENT_IS_SERVERLESS: Optional[bool] = False

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        values = info.data
        scheme = values.get("DB_SCHEME")
        user = values.get("DB_USER")
        password = values.get("DB_PASSWORD")
        host = values.get("DB_SERVER")
        port = values.get("DB_PORT")
        db_name = values.get("DB_NAME") or ""
        additional_config = values.get("DB_ADDITIONAL_CONFIG")

        if SupportedDB.POSTGRES == values.get("ACTIVE_DB") or SupportedDB.MYSQL == values.get("ACTIVE_DB"):
            return f"{scheme}://{user}:{password}@{host}:{port}/{db_name}?{additional_config}"
        else:
            db_path = get_absolute_path(os.path.join("main", "app", "db"))
            db = os.path.join(db_path, db_name)
            db_url = f"{values.get('DB_SERVER')}{db}?{additional_config}"
            print('db_url: ', db_url)
            return db_url

    model_config = SettingsConfigDict(
        # The selector name is lowercase by contract — conftest.py, docker-compose,
        # the CI workflows, and the Vercel deploy flags all set `appodus_active_env`.
        # Linux env vars are case-sensitive (only Windows tolerates a mismatch).
        env_file=get_absolute_path(f'.env.{os.getenv("appodus_active_env", "dev_personal")}'),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENV_KEY_PATTERN: ClassVar[re.Pattern] = re.compile(r"^[A-Z_][A-Z0-9_]*$")
    def set_env_vars(self, *, overwrite: bool = True, include_none: bool = False) -> None:
        """
        Safely set attributes from a pydantic/settings object as environment variables.

        :param self: object with .dict() (e.g., pydantic BaseSettings instance)
        :param overwrite: if False, do not overwrite existing environment vars
        :param include_none: if True, write 'null' for None values; otherwise skip them
        """
        settings_dict = self.model_dump()

        for key, value in settings_dict.items():
            env_key = key.upper()

            # validate env var name
            if not self.ENV_KEY_PATTERN.match(env_key):
                # skip invalid key names (or optionally sanitize)
                continue

            env_value = self._safe_to_str(value, include_none=include_none)
            if env_value is None:
                continue

            if not overwrite and env_key in os.environ:
                continue

            os.environ[env_key] = env_value

        # Store the whole settings snapshot in-process (NOT in os.environ) so the
        # aggregated secret blob is not leaked via the process environment. Consumers
        # read it through get_full_settings_json().
        global _full_settings_json
        try:
            _full_settings_json = json.dumps(jsonable_encoder(self, by_alias=False), ensure_ascii=False)
        except Exception:
            # swallow problems here; you may want to log
            _full_settings_json = None

    # def set_env_vars(self):
    #     """Set all settings as environment variables."""
    #     for key, value in self.dict().items():
    #         os.environ[key.upper()] = str(value)
    #
    #     # Set the whole object, for use in this utils project
    #     settings_dict = jsonable_encoder(self)
    #     os.environ["APPODUS_SETTINGS"] = json.dumps(settings_dict)

    def _safe_to_basic(self, value: Any) -> Any:
        """
        Convert arbitrary python/pydantic value into JSON-serializable
        basic Python types (primitives, lists, dicts) with some special
        handling (enums, dates, decimals, bytes).
        """
        # None
        if value is None:
            return None

        # Enum -> underlying value
        if isinstance(value, enum.Enum):
            return self._safe_to_basic(value.value)

        # Primitives
        if isinstance(value, (str, int, float, bool)):
            return value

        # Dates / datetimes
        if isinstance(value, (datetime, date)):
            return value.isoformat()

        # Decimal -> plain numeric string (no Decimal() wrapper)
        if isinstance(value, Decimal):
            # keep as numeric-like string so json will encode it as a string unless converted elsewhere
            return format(value, "f")

        # Bytes -> base64 w/ prefix so caller can detect and decode
        if isinstance(value, (bytes, bytearray)):
            return "base64:" + base64.b64encode(bytes(value)).decode("ascii")

        # Path, UUID
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, UUID):
            return str(value)

        # Iterable containers (list/tuple/set) -> convert items recursively -> list
        if isinstance(value, (list, tuple, set)):
            return [self._safe_to_basic(v) for v in value]

        # Dict -> convert keys to str and values recursively
        if isinstance(value, dict):
            return {str(k): self._safe_to_basic(v) for k, v in value.items()}

        # pydantic BaseModel (and other special objects) -> jsonable_encoder fallback
        try:
            from pydantic import BaseModel  # lazy import to avoid top-level dep issues
            if isinstance(value, BaseModel):
                return jsonable_encoder(value, by_alias=False)
        except Exception:
            pass

        # Final fallback: try jsonable_encoder then str
        try:
            return jsonable_encoder(value, by_alias=False)
        except Exception:
            return str(value)

    def _safe_to_str(self, value: Any, include_none: bool = False) -> Optional[str]:
        """
        Convert a python value to a string safe for env vars.
        - For primitives: return string representation (bool -> 'true'/'false')
        - For dict/list: return JSON string
        - For None: return None (or 'null' if include_none is True)
        """
        basic = self._safe_to_basic(value)

        if basic is None:
            return "null" if include_none else None

        # booleans -> lowercase 'true'/'false'
        if isinstance(basic, bool):
            return "true" if basic else "false"

        # strings, ints, floats -> plain str
        if isinstance(basic, (str, int, float)):
            return str(basic)

        # lists/dicts/other complex -> JSON encode
        try:
            return json.dumps(basic, ensure_ascii=False)
        except (TypeError, ValueError):
            # as last resort fall back to str()
            return str(basic)
