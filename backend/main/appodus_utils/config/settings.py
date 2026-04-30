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
from pydantic import Field, field_validator, ValidationInfo
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
    LOCAL = "local"

class TemplatingEngine(str, enum.Enum):
    JINJA2 = "jinja2"


class AppodusBaseSettings(BaseSettings):
    BRAND: str = "appodus"
    BRAND_SUPPORT_EMAIL: str = "kingsley.ezenwwere@gmail.com"
    BRAND_SUPPORT_PHONE: str = "2347039018727"

    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    ALLOW_AUTH_BYPASS: bool = False  # Optional
    ENABLE_OUT_MESSAGING: bool = False
    BASE_DIR: str = str(Path(__file__).parent.parent) # Used for accessing local files, e.g message templates

    APP_DOMAIN: str = "http://localhost:8000"
    SHOW_API: bool = True

    # APPODUS
    APPODUS_SERVICES_URL: str = "https://8d39e6e80670.ngrok-free.app"
    APPODUS_CLIENT_ID: str = "b91b0ecb-7bd7-4630-91cb-af20549c8667"
    APPODUS_CLIENT_SECRET: str = "kQWzK2eeNM_9uN16ZmbHCdJNRSw9UQ5eF2PhwqZRz2I="
    APPODUS_CLIENT_SECRET_ENCRYPTION_KEY: str = '1dXgFqcjihJaeCBIYWZf-kjWvBbXkBpxT-5IOWY-G0Y='

    APPODUS_CLIENT_REQUEST_EXPIRES_SECONDS: Optional[int] = 60 * 5 # 5mins

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

    # TOKEN
    ACCESS_TOKEN_TTL_SECONDS: int = 60 * 15  # 15 mins
    REFRESH_TOKEN_TTL_SECONDS: int = 60 * 60 * 24 * 30  # 30 days
    PASSWORD_RESET_TTL_SECONDS: int = 60 * 60  # 1 hour

    OTP_TOKEN_EXPIRE_SECONDS: Optional[int] = 60 * 5 # 5 mins
    EMAIL_OTP_TOKEN_EXPIRE_SECONDS: Optional[int] = 60 * 30 # 30 mins
    CACHE_DATA_EXPIRES_SECONDS: Optional[int] = 60 * 60 * 24 * 8 # Redis Default

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
    APPLE_AUTH_BASE_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
    APPLE_TEAM_ID: Optional[str] = "mock_value"
    APPLE_CLIENT_ID: Optional[str] = "mock_value"
    APPLE_KEY_ID: Optional[str] = "mock_value"
    APPLE_PRIVATE_KEY: Optional[str] = "mock_value"

    # AUTHJWT
    AUTHJWT_SECRET_KEY: str = "auth_jwt_s3cr3t"
    # Configure application to store and get JWT from cookies
    AUTHJWT_TOKEN_LOCATION: List[str] = Field(default_factory=lambda: ["cookies"])
    # Only allow JWT cookies to be sent over https
    AUTHJWT_COOKIE_SECURE: bool = True
    # Enable csrf double submit protection. default is True
    AUTHJWT_COOKIE_CSRF_PROTECT: bool = True
    # Change to 'lax' in production to make your website more secure from CSRF Attacks, default is None
    AUTHJWT_COOKIE_SAMESITE: str = 'none' # Must be 'none' when AUTHJWT_COOKIE_SECURE = True
    # AUTHJWT_ACCESS_COOKIE_KEY: str = 'Host-access_token'
    # AUTHJWT_REFRESH_COOKIE_KEY: str = 'Host-refresh_token'
    # AUTHJWT_ALGORITHM: str = ""

    # MESSAGING
    EMAIL_FROM_ADDRESS: Optional[str] = "noreply@example.com"
    EMAIL_FROM_NAME: str = "veriprops"
    EMAIL_SUBJECTS: Dict[str, str] = {
        "2fa_subject": "Extra Security: Your 2FA Code Inside",
        "account_activation_subject": "Important: Your Account Status",
        "account_deactivation_subject": "Important: Your Account Status",
        "email_verification_subject": "One Quick Step: Verify Your Email",
        "login_diff_device_security_alert_subject": "New Login Detected - Was This You?",
        "name_update_success_subject": "Your Name Has Been Updated ✅",
        "new_feature_announcement_subject": "Exciting New Features Just Launched!",
        "new_user_email_verification_subject": "One Quick Step: Verify Your Email",
        "new_user_welcome_subject": "Welcome to Your Real Estate Journey! 🏡",
        "password_reset_request_subject": "Reset Your Password - Quick & Easy",
        "password_update_success_subject": "Your Password Has Been Updated ✅",
        "phone_verification_subject": "Verify Your Phone - Stay Secure",
    }
    SMS_SENDER_ID: Optional[str] = "veriprops"
    SMS_TTL: int = 25000
    MESSAGE_TEMPLATE_DIR: str = "resources/templates"
    MESSAGING_BRAND_NAME: str = "appodus"

    MESSAGING_HEADERS: List[str] = []
    MESSAGING_PRIORITY: int = 2
    MESSAGING_SANDBOX_MODE: bool = False
    MESSAGING_CATEGORIES: List[str] = []

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
    DB_ENABLE_LOGS: Optional[bool] = True
    DB_ENABLE_LOG_POOL: Optional[bool] = True
    DB_MAIN_THREAD_CONTEXT_ID: int = 12345
    DEPLOYMENT_IS_SERVERLESS: Optional[bool] = True

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
        env_file=get_absolute_path(f'.env.{os.getenv("appodus_active_env", "local")}'),
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

        # store whole settings as JSON (structured) for consumers that want the full object
        try:
            full = json.dumps(jsonable_encoder(self, by_alias=False), ensure_ascii=False)
            os.environ["APPODUS_SETTINGS"] = full
        except Exception:
            # swallow problems here; you may want to log
            pass

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
