from datetime import timedelta
from typing import Optional

from httpx import AsyncClient
from jose import jwt
from kink import di, inject
from starlette.requests import Request

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

httpx_client: AsyncClient = di[AsyncClient]

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
        # Verify the id_token signature against Apple's published JWKS.
        jwks_response = await httpx_client.get("https://appleid.apple.com/auth/keys")
        jwks_response.raise_for_status()
        claims = jwt.decode(
            id_token,
            key=jwks_response.json(),
            algorithms=["RS256"],
            audience=self._client_id,
            issuer="https://appleid.apple.com",
        )

        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=claims.get("sub"),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
        )
