"""Auth-domain DTOs (request/response shapes — no ORM models of its own)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr, Field

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.consent.models import  UserConsentInputDto
from main.app.domain.user.models import UserPersona, UserType
from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


class OtpChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"

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
    intent: Optional[str] = None
    device_fingerprint: Optional[str] = None



class OtpSendDto(Object):
    channel: OtpChannel
    email: Optional[EmailStr] = None
    country_code: Optional[str] = None
    dial_code: Optional[str] = None
    phone: Optional[str] = None

    fullname: Optional[str] = None


class OtpVerifyDto(OtpSendDto):
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
