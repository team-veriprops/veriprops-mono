from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from kink import di
from libre_fastapi_jwt import AuthJWT
from starlette.requests import Request

from main.app.domain.user.auth.session.models import DeviceSessionDto, SecurityEventDto, AuthSessionDto, LoginRequestDto
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils
from main.app.domain.user.service import UserService
from main.app.config.settings import settings
from main.appodus_utils import Utils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import Page, SuccessResponse
from main.appodus_utils.exception.exceptions import UnauthorizedException

session_router = APIRouter(prefix="/sessions", tags=["Sessions"])

user_service: UserService = di[UserService]
session_service: SessionService = di[SessionService]

# Per-IP throttle on login to blunt credential stuffing / account-lockout DoS (M7).
_login_rate_limit = RateLimiter(scope="login", limit=10, window_seconds=60)


def _to_device_dto(s, current_token_hash: Optional[str]) -> DeviceSessionDto:
    return DeviceSessionDto(
        id=str(s.id),
        device=s.device,
        browser=s.browser,
        os=s.os,
        ip_address=s.ip_address,
        approx_location=s.approx_location,
        current=bool(current_token_hash and s.refresh_token_hash == current_token_hash),
        last_active_at=s.last_active_at,
        date_created=s.date_created,
    )

@session_router.post("", response_model=SuccessResponse[AuthSessionDto])
async def login(
    req: LoginRequestDto,
    request: Request,
    authorize: AuthJWT = Depends(),
    _: None = Depends(_login_rate_limit),
):
    user = await session_service.login(
        req, ip_address=ClientUtils.get_client_ip(request), user_agent=ClientUtils.get_user_agent(request),
    )
    session = await session_service.issue_session_cookies(
        user, authorize, ip_address=ClientUtils.get_client_ip(request),
        device=ClientUtils.get_user_agent(request), device_fingerprint=req.device_fingerprint,
    )
    return SuccessResponse[AuthSessionDto](data=session)


@session_router.delete("/current", response_model=SuccessResponse[bool])
async def logout(request: Request, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    refresh_cookie = request.cookies.get(settings.AUTHJWT_REFRESH_COOKIE_KEY)
    if refresh_cookie:
        await session_service.revoke_current_device(refresh_cookie)

    await JwtAuthUtils.revoke_token(authorize=authorize)
    return SuccessResponse[bool](data=True)


@session_router.post("/current", response_model=SuccessResponse[bool])
async def refresh_session(request: Request, authorize: AuthJWT = Depends()):
    # The refresh JWT stays valid until expiry, so check the device session too:
    # a revoked one must not refresh. This is what makes device-revoke and
    # reset-time revoke-all actually end a session.
    refresh_cookie = request.cookies.get(settings.AUTHJWT_REFRESH_COOKIE_KEY)
    token_hash = Utils.sha256(refresh_cookie) if refresh_cookie else None
    device = await session_service.get_device_by_token_hash(token_hash) if token_hash else None
    if not device:
        authorize.unset_jwt_cookies()
        raise UnauthorizedException("Session has been revoked. Please sign in again.")

    await JwtAuthUtils.refresh_access_token(authorize=authorize)
    await session_service.touch_device_session(token_hash)
    return SuccessResponse[bool](data=True)


@session_router.get("/current", response_model=SuccessResponse[AuthSessionDto])
async def current_session(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    user = await user_service.get_user_model(user_id)
    session = await session_service.build_session_dto(user)
    return SuccessResponse[AuthSessionDto](data=session)

@session_router.get("", response_model=SuccessResponse[List[DeviceSessionDto]])
async def list_devices(request: Request, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    refresh = request.cookies.get(settings.AUTHJWT_REFRESH_COOKIE_KEY)
    current_hash = Utils.sha256(refresh) if refresh else None
    sessions = await session_service.list_devices(user_id)
    dtos = [_to_device_dto(s, current_hash) for s in sessions]
    return SuccessResponse[List[DeviceSessionDto]](data=dtos)


@session_router.delete("/{session_id}", response_model=SuccessResponse[bool])
async def revoke_device(session_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    await session_service.revoke_device(session_id)
    return SuccessResponse[bool](data=True)


@session_router.delete("", response_model=SuccessResponse[bool])
async def revoke_all_others(scope: str, request: Request, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    refresh = request.cookies.get(settings.AUTHJWT_REFRESH_COOKIE_KEY)
    current_hash = Utils.sha256(refresh) if refresh else None
    if scope != "others":
        raise UnauthorizedException("Unsupported scope.")
    await session_service.revoke_all_other_devices(user_id, current_hash)
    return SuccessResponse[bool](data=True)


@session_router.get("/security/events", response_model=Page[SecurityEventDto])
async def list_security_events(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return await session_service.page_security_events(user_id, page=page, page_size=page_size)
