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

_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_JWKS_CACHE_KEY = "oauth:jwks:google"
_GOOGLE_VALID_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

httpx_client: AsyncClient = di[AsyncClient]


async def _get_google_jwks() -> dict:
    raw = await RedisUtils.get_redis(_GOOGLE_JWKS_CACHE_KEY)
    if raw:
        return json.loads(raw)
    return await _fetch_and_cache_google_jwks()


async def _fetch_and_cache_google_jwks() -> dict:
    response = await httpx_client.get(_GOOGLE_JWKS_URL)
    response.raise_for_status()
    jwks = response.json()
    await RedisUtils.set_redis(_GOOGLE_JWKS_CACHE_KEY, json.dumps(jwks), time_to_live=timedelta(minutes=5))
    return jwks


def _decode_with_google_jwks(id_token: str, jwks: dict, client_id: str) -> dict:
    claims = jwt.decode(
        id_token,
        key=jwks,
        algorithms=["RS256"],
        audience=client_id,
        options={"verify_iss": False},
    )
    # Google issues tokens with either short or full HTTPS issuer form.
    if claims.get("iss") not in _GOOGLE_VALID_ISSUERS:
        raise jose_exceptions.JWTClaimsError("Invalid issuer")
    return claims


async def _verify_google_id_token(id_token: str, client_id: str) -> dict:
    jwks = await _get_google_jwks()
    try:
        return _decode_with_google_jwks(id_token, jwks, client_id)
    except jose_exceptions.JWKError:
        # Known key not in cached JWKS — provider rotated keys; invalidate and retry once.
        await RedisUtils.delete(_GOOGLE_JWKS_CACHE_KEY)
        jwks = await _fetch_and_cache_google_jwks()
        return _decode_with_google_jwks(id_token, jwks, client_id)


@inject
@decorate_all_methods(method_trace_logger)
class GoogleAuthProvider(ISocialAuthProvider):
    def __init__(self):
        self._client_id = Utils.get_from_env_fail_if_not_exists("GOOGLE_CLIENT_ID")
        self._client_secret = Utils.get_from_env_fail_if_not_exists("GOOGLE_CLIENT_SECRET")
        self._auth_base_url = Utils.get_from_env_fail_if_not_exists("GOOGLE_AUTH_BASE_URL")

    @property
    def platform(self):
        return SocialAuthProvider.GOOGLE

    async def initialize(
        self,
        request: Request,
        intent: Optional[str] = None,
        mode: OAuthFlowMode = OAuthFlowMode.AUTH,
        link_user_id: Optional[str] = None,
    ) -> str:
        scope = "openid email profile"
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
        token_response = await httpx_client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": payload.redirect_uri,
                "code_verifier": payload.code_verifier,
            }
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        id_token = tokens["id_token"]
        claims = await _verify_google_id_token(id_token, self._client_id)
        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=claims["sub"],
            email=claims["email"],
            email_verified=claims["email_verified"],
            firstname=Utils.upper_first(claims["given_name"]),
            lastname=Utils.upper_first(claims["family_name"]),
        )
