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

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.admin_invitation.models import (
    AcceptInviteRequestDto,
    AcceptInviteResultDto,
    AdminInvitationDto,
    AdminInvitationStatus,
    InviteAdminRequestDto,
    InviteAdminResultDto,
)
from main.app.domain.user.admin_invitation.service import AdminInvitationService
from main.app.domain.user.auth.utils.permissions import (
    Permission,
    require_permission,
)
from main.appodus_utils.db.models import Page, SuccessResponse

logger: Logger = di["logger"]

invitation_service: AdminInvitationService = di[AdminInvitationService]

admin_invitation_router = APIRouter(prefix="/admin-invitations", tags=["Admin Invitations"])


@admin_invitation_router.post(
    "",
    response_model=SuccessResponse[InviteAdminResultDto],
)
async def invite(
    req: InviteAdminRequestDto,
    inviter_admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    result = await invitation_service.invite(
        inviter_admin_id=inviter_admin_id,
        email=req.email,
        sub_role=req.sub_role,
    )
    return SuccessResponse[InviteAdminResultDto](data=result)


@admin_invitation_router.get(
    "",
    response_model=Page[AdminInvitationDto],
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
        authorize.jwt_optional()
    except Exception:
        pass
    current_user_id = authorize.get_jwt_subject()
    result = await invitation_service.accept(req.token, current_user_id=current_user_id)
    return SuccessResponse[AcceptInviteResultDto](data=result)
