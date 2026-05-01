"""OAuth controller — popup-based flow.

Flow:
- Frontend POSTs/GETs `/oauth/{provider}/start` and receives `{authorizationUrl}`.
- Frontend opens a popup with that URL.
- Provider redirects the popup to `/oauth/{provider}/callback` on *this* backend.
- Callback validates state + PKCE, exchanges the code, and returns a small HTML
  page that calls `window.opener.postMessage({type:"oauth_result", success})`
  and self-closes. The HttpOnly session cookie is set on the same response.

Email-collision policy: REJECT. The user must log in with their existing
account, then use the explicit "Link account" button (which starts an OAuth
round-trip in `mode=LINK` with their JWT cookie attached).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.oauth.factory import SocialAuthProviderFactory
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider
from main.app.domain.user.auth.oauth.providers.models import (
    OAuthCallbackRequestDto,
    OAuthFlowMode,
    OAuthRequestStoredState,
    SocialAuthProvider,
)
from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
from main.app.domain.user.auth.oauth.service import OAuthIdentityService
from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.auth.session.service import SessionService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import UserAlreadyExistsException

oauth_router = APIRouter(prefix="/oauth", tags=["OAuth"])
social_auth_service_factory: SocialAuthProviderFactory = di[SocialAuthProviderFactory]

auth_service: AuthService = di[AuthService]
oauth_identity_service: OAuthIdentityService = di[OAuthIdentityService]
session_service: SessionService = di[SessionService]


class OAuthStartResponseDto:
    authorization_url: str


@oauth_router.get("/{provider}/start", response_model=SuccessResponse[dict])
async def init_social_auth(
    request: Request,
    provider: SocialAuthProvider,
    intent: Optional[str] = None,
    mode: OAuthFlowMode = OAuthFlowMode.AUTH,
    authorize: AuthJWT = Depends(),
):
    """Returns `{authorizationUrl}` for the popup to navigate to. When
    `mode=link`, the JWT cookie must be present — we attach the user_id to the
    stored state so the callback can link to the right account."""
    link_user_id: Optional[str] = None
    if mode == OAuthFlowMode.LINK:
        authorize.jwt_required()
        link_user_id = authorize.get_jwt_subject()

    auth_provider: ISocialAuthProvider = social_auth_service_factory.get_auth_provider(provider)
    authorization_url = await auth_provider.initialize(
        request=request, intent=intent, mode=mode, link_user_id=link_user_id,
    )
    return SuccessResponse[dict](data={"authorizationUrl": authorization_url})


@oauth_router.api_route("/{provider}/callback", methods=["GET", "POST"])
async def auth_callback(
    provider: SocialAuthProvider,
    request: Request,
    authorize: AuthJWT = Depends(),
):
    """Provider redirects the popup here. Returns minimal HTML that
    postMessages the opener and self-closes. Apple posts (`response_mode=form_post`),
    others GET — we accept both methods."""
    # Read params from query (GET) or form body (POST — Apple).
    if request.method == "POST":
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")
    else:
        qs = request.query_params
        code = qs.get("code")
        state = qs.get("state")
        error = qs.get("error")

    stored_state: Optional[OAuthRequestStoredState] = await OauthUtils.consume_state(state)
    # If state is missing or unknown we cannot trust the Referer for the
    # postMessage target — fail closed using the first allowlisted origin.
    target_origin = stored_state.frontend_origin if stored_state else (
        OauthUtils.resolve_frontend_origin(request)
    )

    if error or not code or not state:
        return OauthUtils.popup_response(
            success=False, target_origin=target_origin,
            message="Sign-in was cancelled or the request was invalid.",
        )
    if not stored_state or not stored_state.code_verifier:
        return OauthUtils.popup_response(
            success=False, target_origin=target_origin,
            message="Sign-in session expired. Please try again.",
        )

    auth_provider = social_auth_service_factory.get_auth_provider(provider)

    payload = OAuthCallbackRequestDto(
        code=code,
        code_verifier=stored_state.code_verifier,
        redirect_uri=OauthUtils.callback_redirect_uri(provider),
    )

    try:
        user_info = await auth_provider.verify(payload, request)
    except Exception:
        return OauthUtils.popup_response(
            success=False, target_origin=target_origin,
            message="Could not complete sign-in with the provider. Please try again.",
        )

    if not user_info.email or not user_info.id:
        return OauthUtils.popup_response(
            success=False, target_origin=target_origin,
            message="Provider did not return enough information to sign you in.",
        )

    # ── LINK mode: attach this provider identity to the authenticated user ──
    if stored_state.mode == OAuthFlowMode.LINK and stored_state.link_user_id:
        try:
            await auth_service.link_oauth_to_authenticated_user(
                user_id=stored_state.link_user_id,
                provider=provider,
                subject=user_info.id,
                email=user_info.email,
                raw_profile=user_info.model_dump(),
            )
        except Exception:
            return OauthUtils.popup_response(
                success=False, target_origin=target_origin,
                message="Could not link this account. It may already be linked to another user.",
            )
        return OauthUtils.popup_response(success=True, target_origin=target_origin)

    # ── AUTH mode: signup or login ──────────────────────────────────────────
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
        # Email exists with a password account, no link yet → REJECT per spec.
        return OauthUtils.popup_response(
            success=False, target_origin=target_origin,
            message="Account exists. Please log in and link this provider explicitly.",
        )

    # libre_fastapi_jwt (cookie mode) hooks into the response cycle and writes
    # the Set-Cookie headers onto whatever Response we return — so call
    # issue_session_cookies first, then build the popup HTML.
    await session_service.issue_session_cookies(
        user, authorize,
        ip_address=ClientUtils.get_client_ip(request),
        device=ClientUtils.get_user_agent(request),
    )
    return OauthUtils.popup_response(success=True, target_origin=target_origin)


@oauth_router.get("/links", response_model=SuccessResponse[List[str]])
async def list_oauth_links(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    return SuccessResponse[List[str]](data=await oauth_identity_service.list_linked_providers(user_id))


@oauth_router.delete("/links/{provider}", response_model=SuccessResponse[bool])
async def unlink_oauth(provider: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    await auth_service.unlink_oauth(user_id, SocialAuthProvider(provider.lower()))
    return SuccessResponse[bool](data=True)
