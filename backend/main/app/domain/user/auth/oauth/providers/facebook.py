from typing import Optional

from httpx import AsyncClient
from kink import di, inject
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.providers.models import (
    OAuthCallbackRequestDto,
    OAuthFlowMode,
    SocialAuthProvider,
    SocialLoginUserInfoDto,
)
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.exception.exceptions import AppodusBaseException
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

    async def initialize(
        self,
        request: Request,
        intent: Optional[str] = None,
        mode: OAuthFlowMode = OAuthFlowMode.AUTH,
        link_user_id: Optional[str] = None,
    ) -> str:
        # Facebook does not support the OIDC `profile` scope reliably; request
        # `email` (and `public_profile` is implicit) and read fields via /me.
        scope = "email"

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

        user_response = await httpx_client.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,email,first_name,last_name",
                "access_token": token_response.json()["access_token"]
            }
        )
        user_response.raise_for_status()
        user_info = user_response.json()

        email = user_info.get("email")
        if not email:
            # Facebook may omit email if the user denied the scope or signed up
            # via phone-only. We require email for account creation.
            raise AppodusBaseException(message="Facebook did not return an email. Please grant email access and try again.")

        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=user_info["id"],
            email=email,
            email_verified=True,  # Facebook only returns emails it has verified.
            firstname=Utils.upper_first(user_info.get("first_name", "")),
            lastname=Utils.upper_first(user_info.get("last_name", "")),
        )
