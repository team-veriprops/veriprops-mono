from typing import Optional

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

GOOGLE_KEYS = JwksCache("https://www.googleapis.com/oauth2/v3/certs", "oauth:jwks:google")
# Google signs with either the bare or the https form of its issuer.
_GOOGLE_VALID_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

httpx_client: AsyncClient = di[AsyncClient]


async def _verify_google_id_token(id_token: str, access_token: str, client_id: str) -> dict:
    return await verify_id_token(
        id_token, GOOGLE_KEYS, audience=client_id, issuer=_GOOGLE_VALID_ISSUERS, access_token=access_token,
    )


@inject
@decorate_all_methods(method_trace_logger)
class GoogleAuthProvider(ISocialAuthProvider):
    def __init__(self):
        self._client_id = settings.GOOGLE_CLIENT_ID
        self._client_secret = settings.GOOGLE_CLIENT_SECRET
        self._auth_base_url = settings.GOOGLE_AUTH_BASE_URL

    @property
    def platform(self):
        return SocialAuthProvider.GOOGLE

    async def initialize(
        self,
        request: Request,
        intent: Optional[AuthIntent] = None,
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
        access_token = tokens["access_token"]
        claims = await _verify_google_id_token(id_token, access_token, self._client_id)
        return SocialLoginUserInfoDto(
            provider=self.platform,
            id=claims["sub"],
            email=claims["email"],
            email_verified=claims["email_verified"],
            firstname=Utils.upper_first(claims["given_name"]),
            lastname=Utils.upper_first(claims["family_name"]),
        )
