import enum
from typing import Optional, Dict

from main.appodus_utils.config.settings import AppodusBaseSettings, get_absolute_path, FileStorage


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

class EscrowMethod(str, enum.Enum):
    FLUTTERWAVE = "flutterwave"
    PAYSTACK = "paystack"


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

    # PAYMENT
    PAYMENT_REDIRECT_PATH: str = "/redirect"
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
    PAYSTACK_BASE_URL: Optional[str] = "https://api.flutterwave.com/v3"
    PAYSTACK_REDIRECT_URL: Optional[str] = "webhooks/flutterwave/redirect"

    # ACTIVES
    ACTIVE_PAYMENT_METHOD: PaymentMethod = PaymentMethod.FLUTTERWAVE

    # TEMPLATING
    TEMPLATE_ENGINE: Optional[str] = "jinja2"

    # AWS
    AWS_ACCESS_KEY: Optional[str] = "AKIARSU7K5ZHU4J7VY5F"
    AWS_SECRET_ACCESS_KEY: Optional[str] = "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"
    AWS_REGION_NAME: Optional[str] = "us-east-1"
    AWS_S3_BUCKET: Optional[str] = "veriprops-documents"
    AWS_S3_PLATFORM_NAME: Optional[str] = FileStorage.S3
    AWS_S3_PRESIGNED_URL_EXPIRES: int = 60 * 15 # 15 mins

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
    GOOGLE_DOC_PARENT_CONTRACT_ID: str = "1he8Q3Sxs2PSdfoWflNFwlk10MXI7M03QqGW3GdPHuWM"
    GOOGLE_DOC_PARENT_CONTRACT_FOLDER_ID: str = "1lODSM6OMBX4Qan7SPFzJf_zJF6fH9mCA"
    GOOGLE_DOC_PROPERTY_CONTRACT_FOLDER_ID: str = "1VblZfpRnHmQj8DN5nOJNc4C1xbQe9u-h"

    # TWILIO
    TWILIO_ACCOUNT_SID: Optional[str] = ""
    TWILIO_AUTH_TOKEN: Optional[str] = ""
    TWILIO_PHONE_NUMBER: Optional[str] = ""
    # TERMII
    TERMII_API: Optional[str] = 'https://v3.api.termii.com/api'
    TERMII_API_KEY: Optional[str] = 'TL2bCMPbPo55fYGMiFpA0EyBm3oJ998PY88zXjSzPWV07Ht7oPIouZVX1v7oYJ'
    TERMII_API_SECRET_KEY: Optional[str] = 'tsk_zgeb640a2b0320c09048483cpx'
    # SENDGRID
    SENDGRID_API_KEY: Optional[str] = ""
    SENDGRID_API_SECRET: Optional[str] = ""
    # MAILJET
    MAILJET_API_KEY: Optional[str] = 'c7e9d85f278d57415a52e10323b1b599'
    MAILJET_API_SECRET: Optional[str] = '8e09beef376c4858b9eb548c77d899f4'


    # WhatsApp Providers
    WHATSAPP_APP_ID: str = "2959461884217467"
    WHATSAPP_APP_SECRET_KEY: str = "3108b4d84a7a1959d6af3a7debc22f6d"
    WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN: Optional[str] = "webhook_verify_token_s3cr3t"
    # WHATSAPP BUSINESS
    WHATSAPP_API_URL: Optional[str] = "https://graph.facebook.com/v22.0"
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = "766140453239478"
    WHATSAPP_BUSINESS_ACCOUNT_ID: Optional[str] = "1412930669928110"
    WHATSAPP_BUSINESS_ACCESS_TOKEN: Optional[str] = "EAAqDnWpVyHsBPKUESrXNqHGWUs7QqDAmjTVi171tDbZALH08qe5cQ6GeTPZBG8UOuBOA36jDFQmZAdHki76aDVLdbpht89K4VSnrENQIqm5st7ZChvJkx9O387YI5DdEIZBA6TMFOjzZCCQwv50ZAfSMliupcGjiPHznZCu6rjNZC04f0aHuEst0HD4fz9FKsevZAtAAZDZD"

    # PUSH Providers
    # Firebase
    FIREBASE_CREDENTIALS_PATH: Optional[str] = get_absolute_path("service_accounts/firebase-service-account.json")
    # Web Push Configuration
    WEB_PUSH_PRIVATE_KEY: Optional[str] = None
    WEB_PUSH_PUBLIC_KEY: Optional[str] = None
    WEB_PUSH_CONTACT_EMAIL: Optional[str] = "notifications@example.com"
    WEB_PUSH_SUBJECT_EMAIL: Optional[str] = "notifications@example.com"

    # Super Admin
    SUPER_ADMIN_PASSWORD: Optional[str] = None


settings = Settings()
settings.set_env_vars() # Set the env vars in os.environ
