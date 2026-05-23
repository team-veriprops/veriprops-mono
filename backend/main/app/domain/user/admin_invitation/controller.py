"""Admin invitation HTTP routes — PRD Phase 4.

URL shape: `/users/admin-invitations/...`

The /accept endpoint is authentication-aware: it succeeds with no JWT for
new-account or already-admin branches, and requires a JWT for the merge
branch where the invitee already has a non-admin account.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import Optional

from fastapi import APIRouter, Depends, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.admin_invitation.models import (
    AcceptInviteRequestDto,
    AcceptInviteResultDto,
    AdminInvitationStatus,
    InviteAdminRequestDto,
    InviteAdminResultDto, QueryAdminInvitationDto,
)
from main.app.domain.user.admin_invitation.service import AdminInvitationService
from main.app.domain.user.auth.utils.permissions import (
    Permission,
    require_permission,
)
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse
from main.appodus_utils.integrations.messaging.models import (
    EmailRecipient,
    MessageContext,
    MessageRequestRecipient,
)

logger: Logger = di["logger"]

invitation_service: AdminInvitationService = di[AdminInvitationService]

admin_invitation_router = APIRouter(prefix="/admin-invitations", tags=["Admin Invitations"])


@admin_invitation_router.post(
    "",
    response_model=SuccessResponse[InviteAdminResultDto],
)
async def invite(
    req: InviteAdminRequestDto,
    request: Request,
    inviter_admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    result = await invitation_service.invite(
        inviter_admin_id=inviter_admin_id,
        email=req.email,
        sub_role=req.sub_role,
        first_name=req.first_name,
        last_name=req.last_name,
    )
    try:
        from main.app.domain.user.user_messages import AccountSecurityMessages
        acct_msgs = di[AccountSecurityMessages]
        domain = ClientUtils.get_referer_domain(request)
        link = f"{domain}/auth/admin-invite/{result.raw_token}"
        fullname = f"{req.first_name} {req.last_name}".strip()
        await acct_msgs.send_direct_admin_user_invite_message(
            recipient=MessageRequestRecipient(
                email=str(req.email),
                fullname=fullname
            ),
            context={
                MessageContext.FIRST_NAME: req.first_name,
                MessageContext.FULL_NAME: result.inviter_fullname,
                MessageContext.LINK: link,
                MessageContext.VALIDITY: "72 hours",
            },
        )
    except Exception:
        logger.warning("Could not send admin invite email", exc_info=True)
    return SuccessResponse[InviteAdminResultDto](data=result)


@admin_invitation_router.get(
    "",
    response_model=Page[QueryAdminInvitationDto],
)
async def list_invites(
    status: Optional[AdminInvitationStatus] = None,
    _: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    return await invitation_service.list(status=status)


@admin_invitation_router.post(
    "/{invitation_id}/revoke",
    response_model=SuccessResponse[bool],
)
async def revoke(
    invitation_id: str,
    admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    await invitation_service.revoke(invitation_id, admin_id)
    return SuccessResponse[bool](data=True)


@admin_invitation_router.post(
    "/accept",
    response_model=SuccessResponse[AcceptInviteResultDto],
)
async def accept(
    req: AcceptInviteRequestDto,
    authorize: AuthJWT = Depends(),
):
    # Optional auth: accept the request whether or not the caller is signed in;
    # the service decides which branch to take.
    try:
        await authorize.jwt_optional()
    except Exception:
        pass
    current_user_id = str(authorize.get_jwt_subject())
    result = await invitation_service.accept(req.token, current_user_id=current_user_id)
    return SuccessResponse[AcceptInviteResultDto](data=result)
