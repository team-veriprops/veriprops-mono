from datetime import timedelta
from typing import Optional

import jwt
from httpx import AsyncClient
from kink import di, inject
from starlette.requests import Request

from main.app.config.settings import settings
from main.app.domain.user.auth.models import AuthIntent
from main.app.domain.user.auth.oauth.providers.id_token import JwksCache, verify_id_token
from main.app.domain.user.auth.oauth.providers.models import (
    OAuthCallbackRequestDto,
    OAuthFlowMode,
    SocialAuthProvider,
    SocialLoginUserInfoDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils

APPLE_KEYS = JwksCache("https://appleid.apple.com/auth/keys", "oauth:jwks:apple")
_APPLE_ISSUER = "https://appleid.apple.com"

httpx_client: AsyncClient = di[AsyncClient]


async def _decode_apple_id_token(id_token: str, access_token: str, client_id: str) -> dict:
    return await verify_id_token(
        id_token, APPLE_KEYS, audience=client_id, issuer=_APPLE_ISSUER, access_token=access_token,
    )


@inject
@decorate_all_methods(method_trace_logger)
class AppleAuthProvider(ISocialAuthProvider):
    def __init__(self):
        self._client_id = settings.APPLE_CLIENT_ID
        self._iss = settings.APPLE_TEAM_ID
        self._auth_base_url = settings.APPLE_AUTH_BASE_URL
        self._private_key = settings.APPLE_PRIVATE_KEY
        self._key_id = settings.APPLE_KEY_ID

    @property
    def platform(self):
        return SocialAuthProvider.APPLE

    async def initialize(
        self,
        request: Request,
        intent: Optional[AuthIntent] = None,
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
                "exp": int((Utils.datetime_now() + timedelta(seconds=settings.OAUTH_CLIENT_SECRET_JWT_TTL_SECONDS)).timestamp()),
                "aud": _APPLE_ISSUER,
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
        tokens = token_response.json()

        id_token = tokens["id_token"]
        access_token = tokens["access_token"]
        claims = await _decode_apple_id_token(id_token, access_token, self._client_id)

        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=claims.get("sub"),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
        )
