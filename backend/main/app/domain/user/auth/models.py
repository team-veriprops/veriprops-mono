"""Auth-domain DTOs (request/response shapes — no ORM models of its own)."""
from __future__ import annotations

import enum
from typing import List, Optional

from pydantic import EmailStr, Field

from main.app.domain.user.auth.consent.models import UserConsentInputDto
from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


class OtpChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    # WhatsApp account linking (PRD §26.4.4, D46). A separate channel rather than a
    # delivery detail of PHONE: the OTP keys are namespaced by channel, so a code sent to
    # a number over WhatsApp cannot be spent as a signup SMS code for the same number.
    WHATSAPP = "WHATSAPP"


class AuthIntent(str, enum.Enum):
    DEFAULT = "default"  # Customer
    VERIFY = "verify"  # Customer
    AGENT = "agent"  # Agent
    INVITED_ADMIN = "invited-admin"  # Admin


class SignupRequestDto(Object):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    country_code: str
    dial_code: str
    phone: str
    country_of_residence: str
    timezone: str
    preferred_currency: TransactionCurrency = TransactionCurrency.NGN
    consents: List[UserConsentInputDto] = Field(default_factory=list)
    intent: Optional[AuthIntent] = None
    device_fingerprint: Optional[str] = None
    # §17.1 — an optional referral code (from ?ref=…); an unknown code is ignored, never fatal.
    referral_code: Optional[str] = None


class OtpSendDto(Object):
    channel: OtpChannel
    email: Optional[EmailStr] = None
    country_code: Optional[str] = None
    dial_code: Optional[str] = None
    phone: Optional[str] = None

    fullname: Optional[str] = None


class OtpVerifyDto(OtpSendDto):
    code: str


class OtpSendResultDto(Object):
    """What a request for a code tells the caller.

    ``delivered`` is False when dispatch did not complete. The code is stored either way, and a
    transient failure is already recorded RETRYING and re-driven — but the caller should be able
    to say so, rather than present an entry box for a code that may never arrive.
    """

    resend_in: int
    delivered: bool


class PhoneOtpSendDto(Object):
    """Pay-step phone verification for the logged-in user (PRD §10.5).

    The number is optional: omitted, the OTP goes to the number on the profile; supplied,
    the customer is confirming a corrected or newly entered number. Either way the profile
    is only updated once the code is verified."""

    country_code: Optional[str] = None
    dial_code: Optional[str] = None
    phone: Optional[str] = None


class VerifyPhoneDto(PhoneOtpSendDto):
    """The OTP plus the same (optional) number the code was sent to."""

    code: str


class ForgotPasswordDto(Object):
    email: EmailStr


class ResetPasswordDto(Object):
    token: str
    password: str


class SetPasswordDto(Object):
    password: str


class ProfileCompletionDto(Object):
    country_code: str
    dial_code: str
    phone: str
    country_of_residence: str
    timezone: str
    preferred_currency: str = "NGN"
