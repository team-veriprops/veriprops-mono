from typing import Optional, List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT
from starlette.requests import Request

from main.app.domain.user.auth.session.models import DeviceSessionDto, SecurityEventDto, AuthSessionDto, LoginRequestDto
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import UnauthorizedException

session_router = APIRouter(prefix="/sessions", tags=["Sessions"])

user_service: UserService = di[UserService]
session_service: SessionService = di[SessionService]


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
        created_at=s.date_created,
    )

@session_router.post("", response_model=SuccessResponse[AuthSessionDto])
async def login(req: LoginRequestDto, request: Request, authorize: AuthJWT = Depends()):
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
    authorize.jwt_required()
    refresh_cookie = request.cookies.get("refresh_token")
    if refresh_cookie:
        await session_service.revoke_current_device(refresh_cookie)

    await JwtAuthUtils.revoke_token(authorize=authorize)
    return SuccessResponse[bool](data=True)


@session_router.post("/current", response_model=SuccessResponse[bool])
async def refresh_session(authorize: AuthJWT = Depends()):
    await JwtAuthUtils.refresh_access_token(authorize=authorize)
    return SuccessResponse[bool](data=True)


@session_router.get("/current", response_model=SuccessResponse[AuthSessionDto])
async def current_session(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    user = await user_service.get_user_model(user_id)
    session = await session_service.build_session_dto(user)
    return SuccessResponse[AuthSessionDto](data=session)

@session_router.get("", response_model=SuccessResponse[List[DeviceSessionDto]])
async def list_devices(request: Request, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    refresh = request.cookies.get("refresh_token")
    current_hash = Utils.sha256(refresh) if refresh else None
    sessions = await session_service.list_devices(user_id)
    dtos = [_to_device_dto(s, current_hash) for s in sessions]
    return SuccessResponse[List[DeviceSessionDto]](data=dtos)


@session_router.delete("/{session_id}", response_model=SuccessResponse[bool])
async def revoke_device(session_id: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    await session_service.revoke_device(session_id)
    return SuccessResponse[bool](data=True)


@session_router.delete("", response_model=SuccessResponse[bool])
async def revoke_all_others(scope: str, request: Request, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    refresh = request.cookies.get("refresh_token")
    current_hash = Utils.sha256(refresh) if refresh else None
    if scope != "others":
        raise UnauthorizedException("Unsupported scope.")
    await session_service.revoke_all_other_devices(user_id, current_hash)
    return SuccessResponse[bool](data=True)


@session_router.get("/security/events", response_model=SuccessResponse[List[SecurityEventDto]])
async def list_security_events(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    events = await session_service.list_recent_events(user_id)
    dtos = [SecurityEventDto(
        id=str(e.id),
        type=e.type,
        description=e.description,
        ip_address=e.ip_address,
        approx_location=e.approx_location,
        device=e.device,
        occurred_at=e.occurred_at,
    ) for e in events]
    return SuccessResponse[List[SecurityEventDto]](data=dtos)
