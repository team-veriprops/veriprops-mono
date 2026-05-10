"""Auth controller — wires every endpoint the frontend's `AuthService` calls
(see `frontend/src/components/website/auth/libs/auth-service.ts`).

URL shape: `/users/auth/...`
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from main.app.domain.user.auth.consent.controller import consent_router

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.models import (
    ForgotPasswordDto,
    OtpSendDto,
    OtpVerifyDto,
    ProfileCompletionDto,
    ResetPasswordDto,
    SetPasswordDto,
    SignupRequestDto,
)
from main.app.domain.user.auth.oauth.controller import oauth_router
from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.auth.session.controller import session_router
from main.app.domain.user.auth.session.models import AuthSessionDto
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.auth.signup_draft.controller import signup_draft_router
from main.app.domain.user.auth.signup_draft.service import SignupDraftService
from main.appodus_utils import RouterUtils, Utils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.integrations.messaging.models import MessageRequestRecipient, EmailRecipient, MessageContext

auth_service: AuthService = di[AuthService]
# consent_service: ConsentService = di[ConsentService]
session_service: SessionService = di[SessionService]
signup_draft_service: SignupDraftService = di[SignupDraftService]
# otp_delivery: OtpDeliveryService = di[OtpDeliveryService]
# kv: KeyValueService = di[KeyValueService]

auth_router = APIRouter(prefix="/auth", tags=["Auths"])

RouterUtils.add_routers(auth_router, [
    consent_router,
    oauth_router,
    session_router,
    signup_draft_router,
])

logger: Logger = di["logger"]


# ─── Signup / Profile completion ─────────────────────────────

@auth_router.post("/signup", response_model=SuccessResponse[AuthSessionDto], status_code=HTTPStatus.CREATED)
async def signup(req: SignupRequestDto, request: Request, authorize: AuthJWT = Depends()):
    user = await auth_service.signup(req, ip_address=ClientUtils.get_client_ip(request))
    session = await session_service.issue_session_cookies(
        user, authorize, ip_address=ClientUtils.get_client_ip(request),
        device=ClientUtils.get_user_agent(request), device_fingerprint=req.device_fingerprint,
    )
    # Server-side signup draft is no longer needed once the account is created.
    try:
        await signup_draft_service.discard(req.email)
    except Exception:
        logger.warning("Could not discard signup draft after successful signup", exc_info=True)
    return SuccessResponse[AuthSessionDto](data=session)


@auth_router.post("/profile/complete", response_model=SuccessResponse[AuthSessionDto])
async def profile_complete(req: ProfileCompletionDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    user = await auth_service.complete_profile(user_id, req)
    return SuccessResponse[AuthSessionDto](data=await session_service.build_session_dto(user))


# ─── OTP ───────────────────────────────────────────────────────────

@auth_router.post("/otp/send", response_model=SuccessResponse[dict])
async def send_otp(req: OtpSendDto, request: Request):
    resend_in = await auth_service.send_otp(
        req.channel,
        email=req.email,
        dial_code=req.dial_code,
        phone=req.phone,
        ip_address=ClientUtils.get_client_ip(request),
        fullname=req.fullname
    )
    return SuccessResponse[dict](data={"resend_in": resend_in})


@auth_router.post("/otp/verify", response_model=SuccessResponse[dict])
async def verify_otp(req: OtpVerifyDto, request: Request):
    await auth_service.verify_otp(
        req.channel, req.code,
        email=req.email, dial_code=req.dial_code, phone=req.phone,
        ip_address=ClientUtils.get_client_ip(request),
    )
    return SuccessResponse[dict](data={"verified": True})


# ─── Password ──────────────────────────────────────────────────────

@auth_router.post("/password/forgot", response_model=SuccessResponse[bool])
async def forgot_password(req: ForgotPasswordDto, request: Request):
    raw_token, fullname = await auth_service.request_password_reset(req.email, ip_address=ClientUtils.get_client_ip(request))
    if raw_token:
        try:
            from main.app.domain.user.user_messages import AccountSecurityMessages
            account_security_messages = di[AccountSecurityMessages]

            domain = ClientUtils.get_referer_domain(request)
            link = f"{domain}/auth/reset-password/{raw_token}"
            firstname, _, lastname = Utils.parse_fullname(fullname)

            await account_security_messages.send_direct_password_reset_request_message(
                recipient=MessageRequestRecipient(
                    email=EmailRecipient(email=req.email, fullname=fullname)
                ),
                context={
                    MessageContext.FULL_NAME: fullname,
                    MessageContext.FIRST_NAME: firstname,
                    MessageContext.LAST_NAME: lastname,
                    MessageContext.LINK: link,
                    MessageContext.VALIDITY: "1 hour",
                }
            )
        except Exception as e:
            logger.warning("Could not send password reset email: {}", e, exc_info=True)
    return SuccessResponse[bool](data=True)


@auth_router.post("/password/reset", response_model=SuccessResponse[bool])
async def reset_password(req: ResetPasswordDto, authorize: AuthJWT = Depends()):
    await auth_service.reset_password(req.token, req.password)
    authorize.unset_jwt_cookies()
    return SuccessResponse[bool](data=True)


@auth_router.post("/password/set", response_model=SuccessResponse[bool])
async def set_password(req: SetPasswordDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    await auth_service.set_password(user_id, req.password)
    return SuccessResponse[bool](data=True)
