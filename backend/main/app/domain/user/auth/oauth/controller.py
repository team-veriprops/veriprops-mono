from typing import Optional, List

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from kink import di
from libre_fastapi_jwt import AuthJWT
from starlette.responses import RedirectResponse

from main.app.domain.user.auth.oauth.factory import SocialAuthProviderFactory
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.models import LinkOAuthDto
from main.app.domain.user.auth.oauth.providers.models import OAuthRequestStoredState, OAuthCallbackRequestDto, \
    SocialAuthProvider
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
from main.app.domain.user.auth.oauth.service import OAuthIdentityService
from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.auth.session.service import SessionService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.exception.exceptions import UserAlreadyExistsException, InvalidTokenException

oauth_router = APIRouter(prefix="/oauth", tags=["OAuth"])
social_auth_service_factory: SocialAuthProviderFactory = di[SocialAuthProviderFactory]

auth_service: AuthService = di[AuthService]
oauth_identity_service: OAuthIdentityService = di[OAuthIdentityService]
session_service: SessionService = di[SessionService]


@oauth_router.get("/{provider}/start")
async def init_social_auth(request: Request, provider: SocialAuthProvider, intent: Optional[str] = None):
    auth_provider: ISocialAuthProvider = social_auth_service_factory.get_auth_provider(provider)

    return await auth_provider.initialize(request, intent)


@oauth_router.get("/{provider}/callback")
async def auth_callback(
        provider: SocialAuthProvider,
        request: Request,
        code: str = None,
        state: str = None,
        error: Optional[str] = None,
        authorize: AuthJWT = Depends()
):
    if error or not code or not state:
        redirect_uri = await OauthUtils.frontend_callback(request=request, intent=None, error=error or "missing_code")
        return RedirectResponse(redirect_uri)

    # Verify state
    state_key = f"oauth:state:{state}"
    stored_state: OAuthRequestStoredState = await RedisUtils.get_redis(state_key)
    await RedisUtils.delete(state_key)

    if not stored_state or not stored_state.code_verifier:
        redirect_uri = await OauthUtils.frontend_callback(request=request, intent=None, error=error or "missing_code")
        return RedirectResponse(redirect_uri)

    auth_provider = social_auth_service_factory.get_auth_provider(provider)

    payload = OAuthCallbackRequestDto(
        code=code,
        code_verifier=stored_state.code_verifier,
    )

    try:
        user_info = await auth_provider.verify(payload, request)
    except Exception:
        redirect_uri = await OauthUtils.frontend_callback(request=request, intent=stored_state.intent,
                                                          error="exchange_failed")
        return RedirectResponse(redirect_uri)

    if not user_info.email or not user_info.id:
        redirect_uri = await OauthUtils.frontend_callback(request=request, intent=stored_state.intent,
                                                          error="missing_userinfo")
        return RedirectResponse(redirect_uri)

    try:
        user, _is_new = await auth_service.find_or_create_oauth_user(
            provider=provider,
            subject=user_info.id,
            email=user_info.email,
            first_name=user_info.firstname,
            last_name=user_info.lastname,
            avatar_url=user_info.picture,
            raw_profile=user_info.model_dump(),
            intent=stored_state.intent,
        )
    except UserAlreadyExistsException:
        redirect_uri = await OauthUtils.frontend_callback(request=request, intent=stored_state.intent,
                                                          collision_email=user_info.email)
        return RedirectResponse(redirect_uri)

    await session_service.issue_session_cookies(
        user, authorize,
        ip_address=ClientUtils.get_client_ip(request),
        device=ClientUtils.get_user_agent(request),
    )

    redirect_uri = await OauthUtils.frontend_callback(request=request, intent=stored_state.intent)
    return RedirectResponse(redirect_uri)


@oauth_router.get("/links", response_model=SuccessResponse[List[str]])
async def list_oauth_links(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    return SuccessResponse[List[str]](data=await oauth_identity_service.list_linked_providers(user_id))


@oauth_router.post("/links/link", response_model=SuccessResponse[bool])
async def link_authenticated_oauth(req: LinkOAuthDto, authorize: AuthJWT = Depends()):
    """Used by the email-collision flow: the user logs in with password, then
    confirms linking the social account. The provider's identity must be
    re-fetched server-side via a fresh OAuth round-trip — this endpoint just
    persists the association we already cached during the initial callback."""
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    cached = await RedisUtils.get_redis(f"oauth:pending_link:{user_id}:{req.provider.value}")
    if not cached:
        raise InvalidTokenException("No pending OAuth link found. Re-initiate the link from your account.")
    await auth_service.link_oauth_to_authenticated_user(
        user_id=user_id,
        provider=req.provider,
        subject=cached.get("subject", ""),
        email=cached.get("email"),
        raw_profile=cached,
    )
    await RedisUtils.delete(f"oauth:pending_link:{user_id}:{req.provider.value}")
    return SuccessResponse[bool](data=True)


@oauth_router.delete("/links/{provider}", response_model=SuccessResponse[bool])
async def unlink_oauth(provider: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    await auth_service.unlink_oauth(user_id, SocialAuthProvider(provider.lower()))
    return SuccessResponse[bool](data=True)
