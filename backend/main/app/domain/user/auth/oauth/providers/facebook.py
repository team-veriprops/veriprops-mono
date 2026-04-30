from typing import Optional

from httpx import AsyncClient
from kink import di, inject
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.providers.models import OAuthCallbackRequestDto, SocialAuthProvider, \
    SocialLoginUserInfoDto
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from starlette.requests import Request

httpx_client: AsyncClient = di[AsyncClient]


@inject
@decorate_all_methods(method_trace_logger)
class FacebookAuthProvider(ISocialAuthProvider):
    def __init__(self):
        self._client_id = Utils.get_from_env_fail_if_not_exists("FACEBOOK_APP_ID")
        self._client_secret = Utils.get_from_env_fail_if_not_exists("FACEBOOK_APP_SECRET")
        self._auth_base_url = Utils.get_from_env_fail_if_not_exists("FACEBOOK_AUTH_BASE_URL")

    @property
    def platform(self):
        return SocialAuthProvider.FACEBOOK

    async def initialize(self, request: Request, intent: Optional[str] = None) -> str:
        scope = "openid email profile"

        return await OauthUtils.init_0auth(platform=self.platform, request=request, base_url=self._auth_base_url, client_id=self._client_id, scope=scope, intent=intent)

    async def verify(self, payload: OAuthCallbackRequestDto, request: Request) -> SocialLoginUserInfoDto:
        # Exchange code for token
        token_response = await httpx_client.get(
            "https://graph.facebook.com/v22.0/oauth/access_token",
            params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": payload.redirect_uri,
                "code": payload.code,
                "code_verifier": payload.code_verifier,
            }
        )
        token_response.raise_for_status()

        # Get user info
        user_response = await httpx_client.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,email,first_name,last_name",
                "access_token": token_response.json()["access_token"]
            }
        )
        user_response.raise_for_status()
        user_info = user_response.json()

        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=user_info["id"],
            email_verified=user_info["email_verified"],
            email=user_info["email"],
            firstname=Utils.upper_first(user_info["first_name"]),
            lastname=Utils.upper_first(user_info["last_name"]),
        )
