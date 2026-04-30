from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import urllib.parse
from typing import Optional, Dict
from urllib.parse import urlencode, urlparse, urlunparse

from kink import di
from starlette.requests import Request

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider, OAuthRequestStoredState
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger

logger: Logger = di["logger"]


@decorate_all_methods(method_trace_logger)
class OauthUtils:

    @staticmethod
    async def init_0auth(platform: SocialAuthProvider, request: Request, base_url: str, client_id: str, scope: str, intent: Optional[str] = None) -> str:
        code_challenge, code_verifier, state = JwtAuthUtils.generate_pkce()
        redirect_uri = await OauthUtils.get_auth_redirect_url(request=request)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        oauth_request_payload = OAuthRequestStoredState(
            code_verifier=code_verifier,
            intent=intent or "default",
        )

        await RedisUtils.set_redis(f"oauth:state:{state}", oauth_request_payload)

        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"

    @staticmethod
    async def get_auth_redirect_url(request: Request, params: dict=None) -> str:
        """
        The redirect url is similar to the init url, when we remove the tailing /init
        :param platform:
        :param request:
        :return:
        """
        # Parse the incoming URL parts
        if params is None:
            params = {}
        path = request.url.path.rsplit("/", 1)[0] # Remove the /start in '/api/users/auths/socials/google/start'
        path = f"{path}/callback" # We're redirecting to our proxy first (NextJS or any other)

        # Use our proxy origin e.g http://appodus.com
        domain = ClientUtils.get_referer_domain(request)
        parsed_referer_url = urlparse(domain)
        query = urlencode(params)

        full_url = urlunparse((
            parsed_referer_url.scheme,
            parsed_referer_url.netloc,
            path,
            "",  # params
            query,  # query
            ""  # fragment
        ))

        return full_url

    @staticmethod
    async def frontend_callback(request: Request, intent: Optional[str], error: Optional[str] = None, collision_email: Optional[str] = None) -> str:
        params: Dict[str, str] = {}
        if intent:
            params["intent"] = intent
        if error:
            params["error"] = error
        if collision_email:
            params["collision_email"] = collision_email
        return await OauthUtils.get_auth_redirect_url(request=request, params=params)
