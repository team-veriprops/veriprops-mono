from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils
from main.app.domain.user.models import User
from main.appodus_utils.exception.exceptions import UnauthorizedException, InvalidCredentialsException

from kink import di, inject

from main.app.domain.user.auth.session.models import (
    CreateDeviceSessionDto,
    CreatePasswordResetTokenDto,
    CreateSecurityEventDto,
    DeviceSession,
    PasswordResetToken,
    SecurityEvent,
    SecurityEventType,
    UpdateDeviceSessionDto,
    UpdatePasswordResetTokenDto, LoginRequestDto, AuthSessionDto, SessionUserDto, UserType, UserPersona,
)
from main.app.domain.user.auth.session.repo import (
    DeviceSessionRepo,
    PasswordResetTokenRepo,
    SecurityEventRepo,
)
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di["logger"]


def _user_to_session_dto(user: User, has_password: bool, linked: List[str]) -> SessionUserDto:

    return SessionUserDto(
        id=str(user.id),
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        email_verified=bool(user.email_verified),
        phone=user.phone,
        phone_country_code=user.phone_country_code,
        phone_dial_code=user.phone_dial_code,
        phone_verified=bool(user.phone_verified),
        country_of_residence=user.country_of_residence,
        timezone=user.timezone,
        preferred_currency=user.preferred_currency,
        user_type=UserType(user.user_type),
        personas=[UserPersona(p) for p in (user.personas or [])],
        admin_sub_role=user.admin_sub_role,
        trust_status=user.trust_status,
        has_password=has_password,
        linked_providers=[SocialAuthProvider(p) for p in linked if p in {sp.value for sp in SocialAuthProvider}],
        avatar_url=user.avatar_url,
        created_at=user.date_created,
    )

@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class SessionService:
    def __init__(
            self,
            device_repo: DeviceSessionRepo,
            event_repo: SecurityEventRepo,
            reset_repo: PasswordResetTokenRepo
    ):
        self._device_repo = device_repo
        self._event_repo = event_repo
        self._reset_repo = reset_repo

    # ── Login ─────────────────────────────────────────────────────
    async def login(
        self,
        req: LoginRequestDto,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[User]:

        from main.app.domain.user.service import UserService
        user_service: UserService = di[UserService]

        user = await user_service.get_user_by_email(req.email)
        now = Utils.datetime_now()

        if user and user.locked_until and user.locked_until > now:
            await self.record_event(
                SecurityEventType.LOGIN_FAILURE,
                "Login attempted on locked account",
                user_id=str(user.id),
                ip_address=ip_address,
                device_fingerprint=req.device_fingerprint,
            )
            raise UnauthorizedException(
                "Account temporarily locked. Try again later.",
            )

        valid = bool(
            user
            and user.password_hash
            and Utils.verify_password(req.password, user.password_hash)
        )
        if not valid:
            if user:
                count = await user_service.increment_failed_login(user)
                # Two attempts before lockout (5 of 7 by default) trigger a
                # WARNING event so the Security Activity Log can highlight an
                # in-progress brute-force attempt.
                warn_at = max(1, settings.AUTH_LOCKOUT_THRESHOLD - 2)
                if count >= settings.AUTH_LOCKOUT_THRESHOLD:
                    until = now + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
                    await user_service.lock_user_until(user, until)
                    await self.record_event(
                        SecurityEventType.ACCOUNT_LOCKED,
                        f"Account locked for {settings.AUTH_LOCKOUT_MINUTES} minutes",
                        user_id=str(user.id),
                        ip_address=ip_address,
                    )
                elif count >= warn_at:
                    await self.record_event(
                        SecurityEventType.LOGIN_FAILURE_WARNING,
                        f"Repeated invalid credentials ({count}/{settings.AUTH_LOCKOUT_THRESHOLD})",
                        user_id=str(user.id),
                        ip_address=ip_address,
                        device_fingerprint=req.device_fingerprint,
                    )
                else:
                    await self.record_event(
                        SecurityEventType.LOGIN_FAILURE,
                        "Invalid credentials",
                        user_id=str(user.id),
                        ip_address=ip_address,
                        device_fingerprint=req.device_fingerprint,
                    )
            else:
                # Don't disclose whether the email exists.
                await self.record_event(
                    SecurityEventType.LOGIN_FAILURE,
                    f"Invalid credentials (unknown email: {req.email})",
                    ip_address=ip_address,
                    device_fingerprint=req.device_fingerprint,
                )
            raise InvalidCredentialsException()

        await user_service.reset_failed_login(user)
        await self.record_event(
            SecurityEventType.LOGIN_SUCCESS,
            "Password sign-in",
            user_id=str(user.id),
            ip_address=ip_address,
            device=user_agent,
            device_fingerprint=req.device_fingerprint,
        )
        return user

    # ── Session/Token issuance ────────────────────────────────────
    async def issue_session_cookies(
                self,
                user: User,
                authorize: AuthJWT,
                *,
                ip_address: Optional[str] = None,
                device: Optional[str] = None,
                device_fingerprint: Optional[str] = None,
        ) -> AuthSessionDto:

        # Persist server-side device session keyed on a hash of the refresh token.
        from typing import cast, Any
        sub_role_value: Any = cast(Any, user).admin_sub_role
        token_hash = JwtAuthUtils.set_access_token(
                user_id=str(user.id),
                user_type=user.user_type,
                user_personas=user.personas,
                authorize=authorize,
                admin_sub_role=str(sub_role_value) if sub_role_value else None,
            )
        await self.create_device_session(CreateDeviceSessionDto(
                user_id=str(user.id),
                refresh_token_hash=token_hash,
                device=device or "Unknown device",
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                last_active_at=Utils.datetime_now(),
            ))

        return await self.build_session_dto(user=user)

    async def build_session_dto(self, user: User) -> AuthSessionDto:

            from main.app.domain.user.auth.oauth.service import OAuthIdentityService
            oauth_identity_service = di[OAuthIdentityService]

            linked = await oauth_identity_service.list_linked_providers(str(user.id))
            return AuthSessionDto(
                access_token_expires_at=Utils.datetime_now_plus(seconds=settings.ACCESS_TOKEN_TTL_SECONDS),
                refresh_token_expires_at=Utils.datetime_now_plus(seconds=settings.REFRESH_TOKEN_TTL_SECONDS),
                user=_user_to_session_dto(user, has_password=bool(user.password_hash), linked=linked),
            )

    async def revoke_current_device(self, refresh_token: str) -> None:
            token_hash = Utils.sha256(refresh_token)
            s = await self.get_device_by_token_hash(token_hash)
            if s:
                await self.revoke_device(str(s.id))

    # ── DeviceSession ─────────────────────────────────────────────
    async def create_device_session(self, dto: CreateDeviceSessionDto) -> DeviceSession:
        await self._device_repo.create(dto)
        return await self._device_repo.get_by_token_hash(dto.refresh_token_hash)

    async def list_devices(self, user_id: str) -> List[DeviceSession]:
        return await self._device_repo.list_for_user(user_id)

    async def revoke_device(self, session_id: str) -> None:
        await self._device_repo.update(
            session_id, UpdateDeviceSessionDto(revoked=True, revoked_at=Utils.datetime_now()),
        )

    async def revoke_all_other_devices(self, user_id: str, current_token_hash: Optional[str]) -> int:
        sessions = await self._device_repo.list_for_user(user_id)
        revoked = 0
        for s in sessions:
            if s.refresh_token_hash == current_token_hash:
                continue
            await self._device_repo.update(
                str(s.id),
                UpdateDeviceSessionDto(revoked=True, revoked_at=Utils.datetime_now()),
            )
            revoked += 1
        return revoked

    async def revoke_all_devices_for_user(self, user_id: str) -> int:
        return await self.revoke_all_other_devices(user_id, current_token_hash=None)

    async def touch_device_session(self, token_hash: str) -> Optional[DeviceSession]:
        s = await self._device_repo.get_by_token_hash(token_hash)
        if not s:
            return None
        await self._device_repo.update(str(s.id), UpdateDeviceSessionDto(last_active_at=Utils.datetime_now()))
        return s

    async def get_device_by_token_hash(self, token_hash: str) -> Optional[DeviceSession]:
        return await self._device_repo.get_by_token_hash(token_hash)

    # ── SecurityEvent ─────────────────────────────────────────────
    async def record_event(
            self,
            type: SecurityEventType,
            description: str,
            *,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            approx_location: Optional[str] = None,
            device: Optional[str] = None,
            device_fingerprint: Optional[str] = None,
    ) -> None:
        await self._event_repo.create(CreateSecurityEventDto(
            user_id=user_id,
            type=type,
            description=description,
            ip_address=ip_address,
            approx_location=approx_location,
            device=device,
            device_fingerprint=device_fingerprint,
            occurred_at=Utils.datetime_now(),
        ))

    async def list_recent_events(self, user_id: str, limit: int = 50) -> List[SecurityEvent]:
        return await self._event_repo.list_recent_for_user(user_id, limit=limit)

    # ── Password reset token ─────────────────────────────────────
    async def create_password_reset_token(
            self, user_id: str, token_hash: str, expires_at: datetime,
    ) -> None:
        await self._reset_repo.create(CreatePasswordResetTokenDto(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at,
        ))

    async def consume_password_reset_token(self, token_hash: str) -> Optional[PasswordResetToken]:
        token = await self._reset_repo.get_by_token_hash(token_hash)
        if not token:
            return None
        if token.expires_at and token.expires_at <= Utils.datetime_now():
            return None
        await self._reset_repo.update(
            str(token.id), UpdatePasswordResetTokenDto(consumed_at=Utils.datetime_now()),
        )
        return token
