from __future__ import annotations

import base64
import hashlib
import secrets
import time
from datetime import timedelta
from typing import TYPE_CHECKING, List

from pydantic import BaseModel

from main.app.config.settings import settings
from main.appodus_utils import Utils

if TYPE_CHECKING:
    from main.app.domain.user.auth.session.models import UserType, UserPersona
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer
from libre_fastapi_jwt import AuthJWT

from kink import di

from main.appodus_utils.common.utils_settings import utils_settings
from main.appodus_utils.db.redis_utils import RedisUtils

logger = di['logger']

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auths/access-token", auto_error=False)

# Revoked access tokens, keyed by jti, kept until the token would have expired anyway.
_DENYLIST_PREFIX = "token_jti"
_REVOKED = "true"
# A token revoked at (or after) its expiry is still recorded, briefly.
_MIN_DENYLIST_TTL_SECONDS = 1


class _JwtSettings(BaseModel):
    authjwt_denylist_enabled: bool = True

    authjwt_secret_key: str = settings.AUTHJWT_SECRET_KEY
    # Pin the signing + accepted-decode algorithm so no algorithm-confusion is possible.
    authjwt_algorithm: str = settings.AUTHJWT_ALGORITHM
    authjwt_decode_algorithms: List[str] = list(settings.AUTHJWT_DECODE_ALGORITHMS)
    authjwt_token_location: List[str] = list(settings.AUTHJWT_TOKEN_LOCATION)
    authjwt_cookie_secure: bool = settings.AUTHJWT_COOKIE_SECURE
    authjwt_cookie_csrf_protect: bool = settings.AUTHJWT_COOKIE_CSRF_PROTECT
    authjwt_cookie_samesite: str = settings.AUTHJWT_COOKIE_SAMESITE

    authjwt_access_cookie_key: str = settings.AUTHJWT_ACCESS_COOKIE_KEY
    authjwt_refresh_cookie_key: str = settings.AUTHJWT_REFRESH_COOKIE_KEY

    authjwt_access_csrf_cookie_key: str = settings.AUTHJWT_ACCESS_CSRF_COOKIE_KEY
    authjwt_refresh_csrf_cookie_key: str = settings.AUTHJWT_REFRESH_CSRF_COOKIE_KEY


class JwtAuthUtils:
    @staticmethod
    @AuthJWT.load_config
    def get_config()-> _JwtSettings:
        return _JwtSettings()

    @staticmethod
    async def check_if_token_in_denylist(decrypted_token) -> bool:
        """Whether the token was revoked (signed out). Fails closed: if the store cannot be
        read, the error propagates and the request gets the standard safe 5xx, rather than an
        unreadable denylist letting a revoked token through."""
        token_jti = decrypted_token['jti']

        jti_key = f"{_DENYLIST_PREFIX}:{token_jti}"
        entry = await RedisUtils.get_redis(jti_key, strict=True)
        return entry == _REVOKED

    @staticmethod
    async def revoke_token(authorize: AuthJWT) -> bool:
        """Deny the current access token for the rest of its life. Raises if the denylist
        write fails, so a caller never reports a sign-out the server did not record."""
        await authorize.jwt_required()
        raw_jwt = authorize.get_raw_jwt() or {}
        token_jti = raw_jwt['jti']

        # `exp` is a unix timestamp; the entry only needs to outlive the token itself.
        remaining = int(raw_jwt.get("exp", 0)) - int(time.time())
        time_to_live = timedelta(seconds=max(remaining, _MIN_DENYLIST_TTL_SECONDS))

        await RedisUtils.set_redis(f"{_DENYLIST_PREFIX}:{token_jti}", _REVOKED, time_to_live, strict=True)

        authorize.unset_jwt_cookies()

        return True

    @staticmethod
    def set_access_token(
            user_id: str,
            user_type: UserType,
            user_personas: List[UserPersona],
            authorize: AuthJWT,
            *,
            admin_sub_role: str | None = None,
    ) -> str:

        refresh_token_expires = timedelta(seconds=utils_settings.REFRESH_TOKEN_TTL_SECONDS)

        user_claims = {
            "user_type": user_type,
            "personas": list(user_personas or []),
            "admin_sub_role": admin_sub_role,
        }

        try:

            access_token = JwtAuthUtils._create_access_token(user_id=user_id, user_claims=user_claims,
                                                             authorize=authorize)
            refresh_token = authorize.create_refresh_token(
                subject=str(user_id),
                expires_time=refresh_token_expires,
                user_claims=user_claims
            )

            authorize.set_access_cookies(access_token)
            authorize.set_refresh_cookies(refresh_token)

            return Utils.sha256(refresh_token)
        except Exception:
            # Never fall through returning an empty hash — that would persist a
            # device-session row with no usable refresh binding and no cookies set.
            # Fail loudly so the login/signup transaction rolls back.
            logger.exception("Failed to issue session tokens")
            raise

    @staticmethod
    async def refresh_access_token(
            authorize: AuthJWT,
            *,
            user_type: UserType,
            user_personas: List[UserPersona],
            admin_sub_role: str | None = None,
    ) -> None:

        await authorize.jwt_refresh_token_required()
        user_id = str(authorize.get_jwt_subject())

        # Claims come from the user record, never from the expiring token. Copying them forward
        # meant a persona granted mid-session never took effect, and one withdrawn mid-session
        # never bit — both surviving for the whole life of the refresh token.
        user_claims = {
            "user_type": user_type,
            "personas": list(user_personas or []),
            "admin_sub_role": admin_sub_role,
        }

        try:

            new_access_token = JwtAuthUtils._create_access_token(user_id=user_id, user_claims=user_claims,
                                                                 authorize=authorize)
            authorize.set_access_cookies(new_access_token)
        except Exception:
            logger.exception("Failed to refresh the access token")
            raise

    @staticmethod
    async def access_token_protected(token: str = Depends(oauth2_scheme), authorize: AuthJWT = Depends()):
        await authorize.jwt_required()
        return authorize

    @staticmethod
    def generate_pkce() -> tuple[str, str, str]:
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('utf-8')

        state  = secrets.token_urlsafe(32)

        return code_challenge, code_verifier, state


    @staticmethod
    def _create_access_token(user_id: str, user_claims: dict, authorize: AuthJWT) -> str:
        access_token_expires = timedelta(seconds=utils_settings.ACCESS_TOKEN_TTL_SECONDS)

        return authorize.create_access_token(
            subject=str(user_id),
            user_claims=user_claims,
            expires_time=access_token_expires,
        )


# Registered here rather than as a decorator: the loader returns None, which would leave the
# method itself unreachable (and untestable) on the class.
AuthJWT.token_in_denylist_loader(JwtAuthUtils.check_if_token_in_denylist)
