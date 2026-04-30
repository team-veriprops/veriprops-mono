from datetime import timedelta
from typing import Optional

from httpx import AsyncClient
from jose import jwt
from kink import di, inject
from starlette.requests import Request

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider, OAuthCallbackRequestDto, \
    SocialLoginUserInfoDto
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

    async def initialize(self, request: Request, intent: Optional[str] = None) -> str:
        scope = "openid email profile"

        return await OauthUtils.init_0auth(platform=self.platform, request=request, base_url=self._auth_base_url, client_id=self._client_id, scope=scope, intent=intent)

    async def verify(self, payload: OAuthCallbackRequestDto, request: Request) -> SocialLoginUserInfoDto:

        # Generate client secret (JWT)
        client_secret = jwt.encode(
            {
                "iss": self._iss,
                "iat": Utils.datetime_now(),
                "exp": Utils.datetime_now() + timedelta(minutes=5),
                "aud": "https://appleid.apple.com",
                "sub": self._client_id
            },
            self._private_key,
            algorithm="ES256",
            headers={"kid": self._key_id}
        )

        # Exchange code for tokens
        token_response = await httpx_client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": self._client_id,
                "client_secret": client_secret,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": payload.redirect_uri
            }
        )

        # Verify ID token
        id_token = token_response.json()["id_token"]
        claims = jwt.decode(
            id_token,
            key="self.config.public_key",
            algorithms=["ES256"],
            audience=self._client_id
        )

        return SocialLoginUserInfoDto(
            provider=self.platform,
            email=claims["email"],
            email_verified=claims["email_verified"],
        )
