"""Admin user-management controller (PRD §4.2). URL shape: /users/admins/users/...

Every endpoint gates on ``Permission.MANAGE_USERS`` (held by SUPER + OPERATIONS).
Enum-typed query params reject free-form filter values at the boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from loguru import Logger

from fastapi import APIRouter, Depends, Query, Request
from kink import di

from main.app.config.settings import settings
from main.app.domain.user.admin_users.models import (
    AdminUserDetailDto,
    AdminUserSummaryDto,
    SetTrustStatusDto,
    SuspendUserDto,
)
from main.app.domain.user.admin_users.service import AdminUsersService
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.user.models import AccountStatus, TrustStatus
from main.appodus_utils import Utils
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse
from main.appodus_utils.integrations.messaging.models import MessageContext, MessageRequestRecipient

admin_users_router = APIRouter(prefix="/admins/users", tags=["Admin Users"])
admin_users_service: AdminUsersService = di[AdminUsersService]

logger: Logger = di["logger"]


@admin_users_router.get("", response_model=SuccessResponse[Page[AdminUserSummaryDto]])
async def list_users(
    query: Optional[str] = Query(default=None),
    persona: Optional[UserPersona] = Query(default=None),
    user_type: Optional[UserType] = Query(default=None),
    trust_status: Optional[TrustStatus] = Query(default=None),
    account_status: Optional[AccountStatus] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    result = await admin_users_service.list_users(
        page=page,
        page_size=page_size,
        query=query,
        persona=persona.value if persona else None,
        user_type=user_type.value if user_type else None,
        trust_status=trust_status.value if trust_status else None,
        account_status=account_status.value if account_status else None,
    )
    return SuccessResponse[Page[AdminUserSummaryDto]](data=result)


@admin_users_router.get("/{user_id}", response_model=SuccessResponse[AdminUserDetailDto])
async def get_user_detail(
    user_id: str,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    result = await admin_users_service.get_user_detail(user_id)
    return SuccessResponse[AdminUserDetailDto](data=result)


@admin_users_router.post("/{user_id}/suspend", response_model=SuccessResponse[bool])
async def suspend_user(
    user_id: str,
    req: SuspendUserDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await admin_users_service.suspend(user_id, reason=req.reason, admin_id=admin_id)
    return SuccessResponse[bool](data=True)


@admin_users_router.post("/{user_id}/reactivate", response_model=SuccessResponse[bool])
async def reactivate_user(
    user_id: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await admin_users_service.reactivate(user_id, admin_id=admin_id)
    return SuccessResponse[bool](data=True)


@admin_users_router.post("/{user_id}/password-reset", response_model=SuccessResponse[bool])
async def force_password_reset(
    user_id: str,
    request: Request,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    issued = await admin_users_service.force_password_reset(user_id, admin_id=admin_id)
    if issued:
        # Same delivery shape as the self-service forgot-password flow (auth/controller.py).
        try:
            from main.app.domain.user.user_messages import AccountSecurityMessages
            account_security_messages = di[AccountSecurityMessages]

            domain = ClientUtils.get_referer_domain(request)
            link = f"{domain}/auth/reset-password/{issued.raw_token}"
            firstname, _, lastname = Utils.parse_fullname(issued.full_name)
            reset_ttl_minutes = settings.PASSWORD_RESET_TTL_SECONDS // 60

            await account_security_messages.send_direct_password_reset_request_message(
                recipient=MessageRequestRecipient(
                    email=issued.email,
                    fullname=issued.full_name,
                ),
                context={
                    MessageContext.FULL_NAME: issued.full_name,
                    MessageContext.FIRST_NAME: firstname,
                    MessageContext.LAST_NAME: lastname,
                    MessageContext.LINK: link,
                    MessageContext.VALIDITY: f"{reset_ttl_minutes} minutes",
                },
                # The link dies with the token — don't retry delivery past it.
                expires_at=Utils.datetime_now_plus(seconds=settings.PASSWORD_RESET_TTL_SECONDS),
            )
        except Exception as e:  # noqa: BLE001 — email delivery is best-effort
            logger.warning("Could not send forced password reset email: {}", e, exc_info=True)
    return SuccessResponse[bool](data=True)


@admin_users_router.post("/{user_id}/trust-status", response_model=SuccessResponse[bool])
async def set_trust_status(
    user_id: str,
    req: SetTrustStatusDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await admin_users_service.set_trust_status(user_id, req.trust_status, admin_id=admin_id)
    return SuccessResponse[bool](data=True)
