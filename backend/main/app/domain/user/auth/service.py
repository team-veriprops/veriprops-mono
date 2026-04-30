"""AuthService — top-level orchestration for signup, login, OAuth, password,
session/device, and consent acceptance. Wired from `controller.py`."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import Optional

from main.app.config.settings import settings
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.oauth.service import OAuthIdentityService
from main.appodus_utils.db.types.money import TransactionCurrency


from kink import di, inject

from main.app.domain.user.auth.models import (
    OtpChannel,
    ProfileCompletionDto,
    SignupRequestDto,
)
from main.app.domain.user.auth.otp_service import OtpService, recipient_for
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.user.auth.session.models import (
    SecurityEventType, UserPersona,
)
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import (
    CreateUserDto,
    UpdateUserDto,
    User,
)
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidTokenException,
    UserAlreadyExistsException,
    ValidationException,
)

logger: Logger = di["logger"]

LOCKOUT_THRESHOLD = 7
LOCKOUT_MINUTES = 15


def _phone_e164(dial_code: str, phone: str) -> str:
    digits = "".join(c for c in (dial_code + phone) if c.isdigit())
    return f"+{digits}"


@inject
@decorate_all_methods(transactional(), exclude=["__init__", "build_session_dto", "_set_cookies", "_unset_cookies"],
                      exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AuthService:
    def __init__(
            self,
            user_service: UserService,
            consent_service: ConsentService,
            session_service: SessionService,
            otp_service: OtpService,
            oauth_identity_service: OAuthIdentityService
    ):
        self._user_service = user_service
        self._consent_service = consent_service
        self._session_service = session_service
        self._otp_service = otp_service
        self._oauth_identity_service = oauth_identity_service

    # ── Signup ────────────────────────────────────────────────────
    async def signup(
            self,
            req: SignupRequestDto,
            *,
            ip_address: Optional[str] = None,
    ) -> User:
        existing = await self._user_service.get_user_by_email(req.email)
        if existing:
            raise UserAlreadyExistsException(email=req.email)

        password_hash = Utils.get_password_hash(req.password)
        # Ensure both consents are present.
        consent_types = {c.document_type for c in req.consents}
        required = {ConsentDocumentType.PLATFORM_TERMS, ConsentDocumentType.PRIVACY_POLICY}
        if not required.issubset(consent_types):
            raise ValidationException(message="Both Platform Terms and Privacy Policy must be accepted.")

        intent_persona = UserPersona.AGENT if req.intent == "agent" else UserPersona.CUSTOMER

        user = await self._user_service.create_user(CreateUserDto(
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            password_hash=password_hash,
            phone=req.phone,
            country_of_residence=req.country_of_residence,
            timezone=req.timezone,
            preferred_currency=req.preferred_currency,
            phone_country_code=req.country_code,
            phone_dial_code=req.dial_code,
            personas=[intent_persona],
            email_verified=True,  # Frontend gated by OTP step, TODO: Fix by confirming stored OTP against user entered values
            phone_verified=True,
        ))

        for consent in req.consents:
            await self._consent_service.record_user_consent(
                user_id=str(user.id),
                document_type=consent.document_type,
                consent_version=consent.consent_version,
                ip_address=ip_address,
                device_fingerprint=req.device_fingerprint,
            )

        await self._session_service.record_event(
            SecurityEventType.LOGIN_SUCCESS,
            "Account created and signed in",
            user_id=str(user.id),
            ip_address=ip_address,
            device_fingerprint=req.device_fingerprint,
        )
        return user

    # ── OAuth ─────────────────────────────────────────────────────
    async def find_or_create_oauth_user(
            self,
            provider: SocialAuthProvider,
            subject: str,
            email: str,
            first_name: str,
            last_name: str,
            avatar_url: Optional[str],
            raw_profile: dict,
            intent: Optional[str],
    ) -> tuple[User, bool]:
        """Returns (user, is_new). Raises if email collision with password account."""
        existing_identity = await self._oauth_identity_service.get_oauth_identity(provider, subject)
        if existing_identity:
            user = await self._user_service.get_user_model(existing_identity.user_id)
            return user, False

        existing_user = await self._user_service.get_user_by_email(email)
        if existing_user:
            if existing_user.password_hash:
                # Collision — caller must redirect user to login + link.
                raise UserAlreadyExistsException(email=email)
            await self._oauth_identity_service.link_oauth(
                str(existing_user.id), provider, subject, email=email, raw_profile=raw_profile,
            )
            return existing_user, False

        intent_persona = UserPersona.AGENT if intent == "agent" else UserPersona.CUSTOMER
        user = await self._user_service.create_user(CreateUserDto(
            first_name=first_name or "Veriprops",
            last_name=last_name or "User",
            email=email,
            password_hash=None,
            phone="0000000000",
            phone_country_code="NG",
            phone_dial_code="+234",
            country_of_residence="NG",
            timezone="Africa/Lagos",
            preferred_currency=TransactionCurrency.NGN,
            personas=[intent_persona],
            email_verified=True,
            phone_verified=False,
        ))
        if avatar_url:
            await self._user_service.update_user(str(user.id), UpdateUserDto(avatar_url=avatar_url))
        await self._oauth_identity_service.link_oauth(
            str(user.id), provider, subject, email=email, raw_profile=raw_profile,
        )
        return user, True

    async def link_oauth_to_authenticated_user(
            self,
            user_id: str,
            provider: SocialAuthProvider,
            subject: str,
            email: Optional[str],
            raw_profile: dict,
    ) -> None:
        await self._oauth_identity_service.link_oauth(user_id, provider, subject, email=email, raw_profile=raw_profile)
        await self._session_service.record_event(
            SecurityEventType.OAUTH_LINKED,
            f"Linked {provider.value} account",
            user_id=user_id,
        )

    async def unlink_oauth(self, user_id: str, provider: SocialAuthProvider) -> None:
        user = await self._user_service.get_user_model(user_id)
        if not user.password_hash:
            raise ValidationException(message="Set a password before unlinking your last sign-in method.")
        await self._oauth_identity_service.unlink_oauth(user_id, provider)
        await self._session_service.record_event(
            SecurityEventType.OAUTH_UNLINKED,
            f"Unlinked {provider.value} account",
            user_id=user_id,
        )

    # ── Profile completion ───────────────────────────────────────
    async def complete_profile(
            self, user_id: str, dto: ProfileCompletionDto,
    ) -> User:
        await self._user_service.update_user(user_id, UpdateUserDto(
            phone_country_code=dto.country_code,
            phone_dial_code=dto.dial_code,
            phone=dto.phone,
            phone_e164=_phone_e164(dto.dial_code, dto.phone),
            phone_verified=True,
            country_of_residence=dto.country_of_residence,
            timezone=dto.timezone,
            preferred_currency=dto.preferred_currency,
        ))
        return await self._user_service.get_user_model(user_id)

    # ── Password ──────────────────────────────────────────────────
    async def request_password_reset(self, email: str, ip_address: Optional[str] = None) -> Optional[tuple[str, str]]:
        """Returns the raw token (for email delivery) — caller must email it.
        Idempotent: never reveals whether the email exists."""
        user = await self._user_service.get_user_by_email(email)
        if not user:
            return None
        raw_token = Utils.random_str(36)
        token_hash = Utils.sha256(raw_token)
        await self._session_service.create_password_reset_token(
            user_id=str(user.id),
            token_hash=token_hash,
            expires_at=Utils.datetime_now_plus(seconds=settings.PASSWORD_RESET_TTL_SECONDS),
        )
        await self._session_service.record_event(
            SecurityEventType.PASSWORD_RESET_REQUESTED,
            "Password reset link generated",
            user_id=str(user.id),
            ip_address=ip_address,
        )

        fullname = " ".join(part for part in [user.first_name, user.last_name] if part)
        return raw_token, fullname

    async def reset_password(self, raw_token: str, new_password: str) -> User:
        token_hash = Utils.sha256(raw_token)
        token = await self._session_service.consume_password_reset_token(token_hash)
        if not token:
            raise InvalidTokenException("This reset link is invalid or has expired.")
        new_hash = Utils.get_password_hash(new_password)
        await self._user_service.set_password_hash(str(token.user_id), new_hash)
        await self._session_service.revoke_all_devices_for_user(str(token.user_id))
        await self._session_service.record_event(
            SecurityEventType.PASSWORD_CHANGED,
            "Password changed via reset link",
            user_id=str(token.user_id),
        )
        return await self._user_service.get_user_model(str(token.user_id))

    async def set_password(self, user_id: str, new_password: str) -> None:
        new_hash = Utils.get_password_hash(new_password)
        await self._user_service.set_password_hash(user_id, new_hash)
        await self._session_service.record_event(
            SecurityEventType.PASSWORD_CHANGED, "Password set",
            user_id=user_id,
        )

    # ── OTP ───────────────────────────────────────────────────────
    async def send_otp(
            self,
            channel: OtpChannel,
            *,
            email: Optional[str] = None,
            dial_code: Optional[str] = None,
            phone: Optional[str] = None,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            fullname: Optional[str] = None,
    ) -> int:
        recipient = recipient_for(channel, email=email, dial_code=dial_code, phone=phone, fullname=fullname)
        return await self._otp_service.send_otp(
            channel, recipient, user_id=user_id, ip_address=ip_address,
        )

    async def verify_otp(
            self,
            channel: OtpChannel,
            code: str,
            *,
            email: Optional[str] = None,
            dial_code: Optional[str] = None,
            phone: Optional[str] = None,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
    ) -> None:
        recipient = recipient_for(channel, email=email, dial_code=dial_code, phone=phone)
        await self._otp_service.verify_otp(
            channel, recipient, code, user_id=user_id, ip_address=ip_address,
        )
