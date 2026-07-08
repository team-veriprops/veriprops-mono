import enum
from typing import Optional, Dict

from main.appodus_utils.config.settings import (
    AppodusBaseSettings,
    SECRET_PLACEHOLDER,
    get_absolute_path,
    FileStorage,
)


class IntegratedPlatform(str, enum.Enum):
    ZOHO_DOC_SIGN = "zoho_doc_sign"
    GOOGLE_DRIVE = "google_drive"
    FLUTTERWAVE = "flutterwave"
    PAYSTACK = "paystack"

class PaymentMethod(str, enum.Enum):
    FLUTTERWAVE = "flutterwave"
    PAYSTACK = "paystack"
    STRIPE = "stripe"

    @property
    def integrated_platform(self) -> Optional[IntegratedPlatform]:
        return PAYMENT_METHOD_TO_PLATFORM.get(self)

PAYMENT_METHOD_TO_PLATFORM: Dict[PaymentMethod, IntegratedPlatform] = {
    PaymentMethod.FLUTTERWAVE: IntegratedPlatform.FLUTTERWAVE,
    PaymentMethod.PAYSTACK: IntegratedPlatform.PAYSTACK,
}

class Settings(AppodusBaseSettings):
    # CORS
    ALLOWED_ORIGINS: Optional[str] = """
    http://192.168.0.107,
    http://192.168.0.107:3000,
    http://localhost,
    http://localhost:3000,
    http://127.0.0.1,
    http://127.0.0.1:3000,
    http://0.0.0.0:3000,
    https://veriprops.ng,
    https://www.veriprops.ng,
    https://staging.veriprops.ng,
    https://dev.veriprops.ng,
    https://test.veriprops.ng,
    https://*.veriprops.ng,
    """

    # OAuth — popup flow
    # Public origin of *this* backend service (used for non-OAuth purposes).
    BACKEND_PUBLIC_ORIGIN: str = "http://localhost:8000"
    # Base URL used to build the OAuth redirect_uri sent to each provider.
    # Must point at the frontend proxy (e.g. http://localhost:3000) so that the
    # provider redirects the popup through Next.js. The proxy forwards the request
    # to this backend transparently, and the Set-Cookie response flows back through
    # the proxy — so the browser receives the cookie on the frontend origin, not
    # the backend origin. Defaults to BACKEND_PUBLIC_ORIGIN when empty (legacy).
    OAUTH_CALLBACK_BASE_URL: str = ""
    # Allowlist of frontend origins permitted to receive postMessage from the
    # OAuth popup callback. The Referer at /start must match one of these
    # exactly (scheme + host + port). Comma-separated.
    OAUTH_FRONTEND_ORIGINS: str = "http://localhost:3000,https://veriprops.ng,https://www.veriprops.ng,https://staging.veriprops.ng,https://dev.veriprops.ng"

    @property
    def oauth_callback_base(self) -> str:
        """Resolved base URL for OAuth redirect_uri construction."""
        return (self.OAUTH_CALLBACK_BASE_URL or self.BACKEND_PUBLIC_ORIGIN).rstrip("/")

    # PAYMENT
    PAYMENT_FRONTEND_REDIRECT_PATH: str = "/payment/redirect"
    # FLUTTERWAVE
    FLUTTERWAVE_PUBLIC_KEY: Optional[str] = "random"
    FLUTTERWAVE_SECRET_KEY: Optional[str] = "random"
    FLUTTERWAVE_WEBHOOK_SECRET: Optional[str] = None  # For verifying webhooks
    FLUTTERWAVE_BASE_URL: Optional[str] = "https://api.flutterwave.com/v3"
    FLUTTERWAVE_REDIRECT_URL: Optional[str] = "webhooks/flutterwave/redirect"
    # PAYSTACK
    PAYSTACK_PUBLIC_KEY: Optional[str] = "random"
    PAYSTACK_SECRET_KEY: Optional[str] = "random"
    PAYSTACK_WEBHOOK_SECRET: Optional[str] = None  # For verifying webhooks
    PAYSTACK_BASE_URL: Optional[str] = "https://api.paystack.co"

    # ACTIVES
    ACTIVE_PAYMENT_METHOD: PaymentMethod = PaymentMethod.FLUTTERWAVE

    # Deterministic payment path for local/test/dev automation (mirrors OTP_MODE):
    # initiation returns a synthetic checkout URL and a stub-confirm endpoint drives
    # PAYMENT_PENDING -> PAID via the idempotent webhook handler, without a live
    # gateway. Must be False in production (real gateway webhooks drive PAID).
    PAYMENT_STUB_MODE: bool = True

    # Toggles the phone-verification step in the email/OAuth signup flow. When off,
    # the number is collected but verified later at the Phase-5 payment step.
    PHONE_VERIFICATION_ENABLED: bool = False

    # TEMPLATING
    TEMPLATE_ENGINE: Optional[str] = "jinja2"

    # AWS — real values live in the git-ignored .env.{env}, never in committed source.
    AWS_ACCESS_KEY: Optional[str] = SECRET_PLACEHOLDER
    AWS_SECRET_ACCESS_KEY: Optional[str] = SECRET_PLACEHOLDER
    AWS_REGION_NAME: Optional[str] = "us-east-1"
    AWS_S3_BUCKET: Optional[str] = "veriprops-documents"
    AWS_S3_PLATFORM_NAME: Optional[str] = FileStorage.S3
    AWS_S3_PRESIGNED_URL_EXPIRES: int = 60 * 15 # 15 mins
    # Deterministic document storage for tests/local (no external calls), like
    # PAYMENT_STUB_MODE. When true, evidence upload uses the stub provider; the
    # content hash + server-stamped GPS/timestamp are computed regardless (§4.5, §7.3a).
    DOCUMENT_STORAGE_STUB_MODE: bool = True

    # Report PDF (S14, §10). The real pure-Python fpdf2 renderer is the default (no
    # native deps / creds); the deterministic stub renderer is selected when True for
    # ultra-fast tests. Mirrors the facade pattern of payment/storage/kyc.
    REPORT_PDF_STUB_MODE: bool = False
    # Public base URL the report PDF's QR deep-links to (public lookup, §10.1/§13).
    PUBLIC_APP_BASE_URL: str = "https://veriprops.ng"
    # Brand name printed on the report cover + PDF (§10.1).
    REPORT_BRAND_NAME: str = "Veriprops"
    # §B go-live gate (D18): the Premium Legal Opinion report section is built but its
    # content stays hidden until NBA counsel sign-off + lawyer-role PI cover. Never
    # default-on. Surfaced to the frontend via GET /config/public.
    LEGAL_OPINION_ENABLED: bool = False

    # ZOHO
    ZOHO_CLIENT_ID: Optional[str] = None
    ZOHO_CLIENT_SECRET: Optional[str] = None
    ZOHO_REFRESH_TOKEN: Optional[str] = None
    ZOHO_DOC_SIGN_DATA_CENTER: Optional[str] = "https://sign.zoho.com"
    ZOHO_WEBHOOK_SECRET: Optional[str] = None

    # GOOGLE DRIVE
    GOOGLE_WEBHOOK_SECRET: Optional[str] = None
    GOOGLE_WEBHOOK_NOTIFICATION_TTL: int = 60 * 60 * 24 # 1 Day
    GOOGLE_DOC_CHANGE_UPDATE_WINDOW: int = 60 * 60 * 24 # 1 Day
    GOOGLE_SERVICE_ACCOUNT_FILE: Optional[str] = get_absolute_path("service_accounts/contracts-service_account.json")
    GOOGLE_DOC_PARENT_CONTRACT_FOLDER_ID: str = "1lODSM6OMBX4Qan7SPFzJf_zJF6fH9mCA"
    GOOGLE_DOC_PROPERTY_CONTRACT_FOLDER_ID: str = "1VblZfpRnHmQj8DN5nOJNc4C1xbQe9u-h"

    # TWILIO
    TWILIO_ACCOUNT_SID: Optional[str] = ""
    TWILIO_AUTH_TOKEN: Optional[str] = ""
    TWILIO_PHONE_NUMBER: Optional[str] = ""
    # TERMII
    TERMII_API: Optional[str] = 'https://v3.api.termii.com/api'
    TERMII_API_KEY: Optional[str] = SECRET_PLACEHOLDER
    TERMII_API_SECRET_KEY: Optional[str] = SECRET_PLACEHOLDER
    # SENDGRID
    SENDGRID_API_KEY: Optional[str] = ""
    SENDGRID_API_SECRET: Optional[str] = ""
    # MAILJET
    MAILJET_API: Optional[str] = 'https://api.mailjet.com'
    MAILJET_API_KEY: Optional[str] = SECRET_PLACEHOLDER
    MAILJET_API_SECRET: Optional[str] = SECRET_PLACEHOLDER


    # WhatsApp Providers — app id / phone / account ids are non-secret identifiers;
    # the app secret, verify token, and access token are secrets and live in .env.{env}.
    WHATSAPP_APP_SECRET_KEY: str = SECRET_PLACEHOLDER
    WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN: Optional[str] = SECRET_PLACEHOLDER
    # WHATSAPP BUSINESS
    WHATSAPP_API_URL: Optional[str] = "https://graph.facebook.com/v22.0"
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = "766140453239478"
    WHATSAPP_BUSINESS_ACCOUNT_ID: Optional[str] = "1412930669928110"
    WHATSAPP_BUSINESS_ACCESS_TOKEN: Optional[str] = SECRET_PLACEHOLDER

    # PUSH Providers
    # Firebase
    FIREBASE_CREDENTIALS_PATH: Optional[str] = get_absolute_path("service_accounts/firebase-service-account.json")
    # Web Push Configuration
    WEB_PUSH_PRIVATE_KEY: Optional[str] = None
    WEB_PUSH_PUBLIC_KEY: Optional[str] = None
    WEB_PUSH_CONTACT_EMAIL: Optional[str] = "notifications@example.com"

    # Super Admin
    SUPER_ADMIN_PASSWORD: Optional[str] = None
    SUPER_ADMIN_EMAIL: Optional[str] = None

    # Geocoding (PRD §5.1) — STUB (deterministic NG fixtures) | GOOGLE_PLACES
    GEOCODING_PROVIDER: Optional[str] = "STUB"

    # KYC (PRD Open Q #15 / #16) — STUB | MONO | DOJAH
    KYC_PROVIDER: Optional[str] = "STUB"
    # Dojah credentials (required when KYC_PROVIDER=DOJAH)
    DOJAH_APP_ID: str = ""
    DOJAH_PRIVATE_KEY: str = ""
    DOJAH_WEBHOOK_SECRET: str = ""
    # Selfie scores below this threshold route to admin UNDER_REVIEW queue (D18)
    KYC_SELFIE_REVIEW_THRESHOLD: int = 80

    # Verification pricing & FX
    PRICING_FX_PROVIDER: Optional[str] = "STUB"  # STUB | OPENEXCHANGERATES
    PRICING_FX_CACHE_SECONDS: int = 5 * 60          # 5 min cache
    PRICING_FX_STALE_AFTER_SECONDS: int = 30 * 60   # 30 min => stale-warning
    PRICE_LOCK_TTL_HOURS: int = 24

    # Admin invitations
    ADMIN_INVITE_TTL_HOURS: int = 72

    # Task assignment, capacity & timeout sweeps (PRD §6.2, §6.5, §7.2)
    AUTO_ASSIGNMENT_ENABLED: bool = False       # broadcast tasks to the open pool at PAID
    AGENT_MAX_ACTIVE_TASKS: int = 5             # capacity cap enforced on assign/accept
    TASK_NO_SHOW_TIMEOUT_HOURS: int = 12        # manual-assign accept deadline
    TASK_POOL_TIMEOUT_HOURS: int = 24           # broadcast starvation timeout
    REMOTE_JOB_BONUS_MINOR: int = 0             # optional flat bonus on aging pool tasks (kobo)

    # Agent commission (PRD §8.3/§15.2, D13) — share of the verification price paid out
    # to agents, split across roles by the Trust Score Weights; accrued at release.
    AGENT_COMMISSION_SHARE: float = 0.40

    # Background scheduler (PRD §6.4/§7.2) — disabled in test; sweeps invoked directly.
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_SWEEP_INTERVAL_SECONDS: int = 15 * 60


settings = Settings()
settings.set_env_vars() # Set the env vars in os.environ
