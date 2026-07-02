"""Admin invitation controller (PRD §4.1). URL shape: /users/admins/invitations/..."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.admin_invitation.models import (
    AdminInvitationSummaryDto,
    InviteAdminRequestDto,
    InvitePreviewDto,
)
from main.app.domain.user.admin_invitation.service import AdminInvitationService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse

admin_invitation_router = APIRouter(prefix="/admins/invitations", tags=["Admin Invitations"])
invitation_service: AdminInvitationService = di[AdminInvitationService]


@admin_invitation_router.post("", response_model=SuccessResponse[dict])
async def invite_admin(
    req: InviteAdminRequestDto,
    request: Request,
    admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    raw_token = await invitation_service.invite(
        email=req.email, sub_role=req.sub_role, invited_by=admin_id,
        ip_address=ClientUtils.get_client_ip(request),
    )
    domain = ClientUtils.get_referer_domain(request)
    invite_url = f"{domain}/auth/admin-invite/{raw_token}"
    # The link is returned to the inviting Super Admin to deliver (email template
    # wiring is a follow-up; in dev the admin shares the link directly).
    return SuccessResponse[dict](data={"inviteUrl": invite_url})


@admin_invitation_router.get("", response_model=SuccessResponse[Page[AdminInvitationSummaryDto]])
async def list_invitations(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    result = await invitation_service.list_invitations(page=page, page_size=page_size)
    return SuccessResponse[Page[AdminInvitationSummaryDto]](data=result)


@admin_invitation_router.post("/{invitation_id}/revoke", response_model=SuccessResponse[bool])
async def revoke_invitation(
    invitation_id: str,
    admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    await invitation_service.revoke(invitation_id, admin_id)
    return SuccessResponse[bool](data=True)


@admin_invitation_router.get("/preview/{token}", response_model=SuccessResponse[InvitePreviewDto])
async def preview_invitation(token: str):
    """Unauthenticated preview so the frontend can route the acceptance flow."""
    preview = await invitation_service.preview(token)
    return SuccessResponse[InvitePreviewDto](data=preview)


@admin_invitation_router.post("/accept", response_model=SuccessResponse[dict])
async def accept_invitation(token: str = Body(..., embed=True), authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    sub_role = await invitation_service.accept(token, user_id)
    return SuccessResponse[dict](data={"subRole": sub_role.value})
