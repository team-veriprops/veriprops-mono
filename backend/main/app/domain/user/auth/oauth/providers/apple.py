import json
from datetime import timedelta
from typing import Optional

from httpx import AsyncClient
from jose import jwt, exceptions as jose_exceptions
from kink import di, inject
from starlette.requests import Request

from main.app.domain.user.auth.oauth.providers.models import (
    OAuthCallbackRequestDto,
    OAuthFlowMode,
    SocialAuthProvider,
    SocialLoginUserInfoDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils

_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_JWKS_CACHE_KEY = "oauth:jwks:apple"

httpx_client: AsyncClient = di[AsyncClient]


async def _get_apple_jwks() -> dict:
    raw = await RedisUtils.get_redis(_APPLE_JWKS_CACHE_KEY)
    if raw:
        return json.loads(raw)
    return await _fetch_and_cache_apple_jwks()


async def _fetch_and_cache_apple_jwks() -> dict:
    response = await httpx_client.get(_APPLE_JWKS_URL)
    response.raise_for_status()
    jwks = response.json()
    await RedisUtils.set_redis(_APPLE_JWKS_CACHE_KEY, json.dumps(jwks), time_to_live=timedelta(minutes=5))
    return jwks


async def _decode_apple_id_token(id_token: str, client_id: str) -> dict:
    jwks = await _get_apple_jwks()
    try:
        return jwt.decode(
            id_token,
            key=jwks,
            algorithms=["RS256"],
            audience=client_id,
            issuer="https://appleid.apple.com",
        )
    except jose_exceptions.JWKError:
        # Key not in cached JWKS — Apple rotated keys; invalidate and retry once.
        await RedisUtils.delete(_APPLE_JWKS_CACHE_KEY)
        jwks = await _fetch_and_cache_apple_jwks()
        return jwt.decode(
            id_token,
            key=jwks,
            algorithms=["RS256"],
            audience=client_id,
            issuer="https://appleid.apple.com",
        )


@inject
@decorate_all_methods(method_trace_logger)
class AppleAuthProvider(ISocialAuthProvider):
    def __init__(self):
        self._client_id = Utils.get_from_env_fail_if_not_exists("APPLE_CLIENT_ID")
        self._iss = Utils.get_from_env_fail_if_not_exists("APPLE_TEAM_ID")
        self._auth_base_url = Utils.get_from_env_fail_if_not_exists("APPLE_AUTH_BASE_URL")
        self._private_key = Utils.get_from_env_fail_if_not_exists("APPLE_PRIVATE_KEY")
        self._key_id = Utils.get_from_env_fail_if_not_exists("APPLE_KEY_ID")

    @property
    def platform(self):
        return SocialAuthProvider.APPLE

    async def initialize(
        self,
        request: Request,
        intent: Optional[str] = None,
        mode: OAuthFlowMode = OAuthFlowMode.AUTH,
        link_user_id: Optional[str] = None,
    ) -> str:
        # Apple requires `name email` (the `profile` alias is not honoured) and
        # delivers the callback as `form_post`. `OauthUtils.init_0auth` adds
        # `response_mode=form_post` for APPLE.
        scope = "name email"

        return await OauthUtils.init_0auth(
            platform=self.platform,
            request=request,
            base_url=self._auth_base_url,
            client_id=self._client_id,
            scope=scope,
            intent=intent,
            mode=mode,
            link_user_id=link_user_id,
        )

    async def verify(self, payload: OAuthCallbackRequestDto, request: Request) -> SocialLoginUserInfoDto:

        # Apple's client_secret is a short-lived JWT signed with the team's private key.
        client_secret = jwt.encode(
            {
                "iss": self._iss,
                "iat": int(Utils.datetime_now().timestamp()),
                "exp": int((Utils.datetime_now() + timedelta(minutes=5)).timestamp()),
                "aud": "https://appleid.apple.com",
                "sub": self._client_id,
            },
            self._private_key,
            algorithm="ES256",
            headers={"kid": self._key_id},
        )

        token_response = await httpx_client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": self._client_id,
                "client_secret": client_secret,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": payload.redirect_uri,
            },
        )
        token_response.raise_for_status()

        id_token = token_response.json()["id_token"]
        claims = await _decode_apple_id_token(id_token, self._client_id)

        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=claims.get("sub"),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
        )
