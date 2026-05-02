from __future__ import annotations

import base64
import hashlib
import secrets
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

from main.appodus_utils.common.utils_settings import utils_settings
from main.appodus_utils.db.redis_utils import RedisUtils

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auths/access-token", auto_error=False)


class _JwtSettings(BaseModel):
    authjwt_secret_key: str = settings.AUTHJWT_SECRET_KEY
    authjwt_token_location: List[str] = list(settings.AUTHJWT_TOKEN_LOCATION)
    authjwt_cookie_secure: bool = settings.AUTHJWT_COOKIE_SECURE
    authjwt_cookie_csrf_protect: bool = settings.AUTHJWT_COOKIE_CSRF_PROTECT
    authjwt_cookie_samesite: str = settings.AUTHJWT_COOKIE_SAMESITE
    authjwt_access_cookie_key: str = "access_token"
    authjwt_refresh_cookie_key: str = "refresh_token"
    authjwt_access_csrf_cookie_key: str = "csrf_access"
    authjwt_refresh_csrf_cookie_key: str = "csrf_refresh"


class JwtAuthUtils:
    @staticmethod
    @AuthJWT.load_config
    def get_config()-> _JwtSettings:
        return _JwtSettings()

    @staticmethod
    @AuthJWT.token_in_denylist_loader
    async def check_if_token_in_denylist(decrypted_token) -> bool:
        token_jti = decrypted_token['jti']

        jti_key = f"token_jti:{token_jti}"
        entry = await RedisUtils.get_redis(jti_key)
        return entry and entry == 'true'

    @staticmethod
    async def revoke_token(authorize: AuthJWT) -> bool:
        authorize.jwt_required()
        token_jti = authorize.get_raw_jwt()['jti']

        # TODO: Get the remaining refresh token TTL (time_to_live) from authorize
        time_to_live = timedelta(seconds=utils_settings.REFRESH_TOKEN_TTL_SECONDS)

        await RedisUtils.set_redis(f"token_jti:{token_jti}", 'true', time_to_live)  # Store until token expires

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
        except Exception as exc:
            print(exc)
            return ""

    @staticmethod
    async def refresh_access_token(authorize: AuthJWT) :

        authorize.jwt_refresh_token_required()
        user_id = authorize.get_jwt_subject()

        # TODO: Get user_claims from authorize
        user_claims = {}

        try:

            new_access_token = JwtAuthUtils._create_access_token(user_id=user_id, user_claims=user_claims,
                                                                 authorize=authorize)
            authorize.set_access_cookies(new_access_token)
        except Exception as exc:
            print(exc)
            raise

    @staticmethod
    async def access_token_protected(token: str = Depends(oauth2_scheme), authorizer: AuthJWT = Depends()):
        authorizer.jwt_required()
        return authorizer

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
