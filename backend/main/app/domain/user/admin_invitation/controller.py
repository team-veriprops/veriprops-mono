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
from main.app.config.settings import settings
from main.app.domain.user.admin_invitation.service import AdminInvitationService
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse

admin_invitation_router = APIRouter(prefix="/admins/invitations", tags=["Admin Invitations"])
logger = di["logger"]
invitation_service: AdminInvitationService = di[AdminInvitationService]
session_service: SessionService = di[SessionService]
user_service: UserService = di[UserService]


@admin_invitation_router.post("", response_model=SuccessResponse[dict])
async def invite_admin(
    req: InviteAdminRequestDto,
    request: Request,
    admin_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    raw_token = await invitation_service.invite(
        email=req.email, sub_role=req.sub_role, invited_by=admin_id,
        first_name=req.first_name, last_name=req.last_name,
        ip_address=ClientUtils.get_client_ip(request),
    )
    domain = ClientUtils.get_referer_domain(request)
    invite_url = f"{domain}/auth/admin-invite/{raw_token}"
    # The link is returned to the inviting Super Admin to deliver.
    # TODO(gap): admin-invitation email — no template sends the link yet — PRD "Known Gaps & Roadmap".
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
async def accept_invitation(request: Request, token: str = Body(..., embed=True), authorize: AuthJWT = Depends()):
    """Take up an admin invitation, and re-mint this session as the admin it now is.

    The session's claims are copied from the user record when it is issued, so without the
    rotation the new admin's token still says customer and every admin route turns them away
    until they sign in again — the same reason taking up the customer hat rotates (§3.2).
    """
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    sub_role = await invitation_service.accept(token, user_id)
    # Best-effort, like the agent-application grant: the elevation is already committed, and the
    # invitation is spent, so a failed rotation must not turn the accept into an error the user
    # cannot retry. Their next sign-in carries the admin claims either way.
    refresh_cookie = request.cookies.get(settings.AUTHJWT_REFRESH_COOKIE_KEY)
    try:
        await session_service.rotate_current_session(
            await user_service.get_user_model(user_id), authorize,
            Utils.sha256(refresh_cookie) if refresh_cookie else None,
        )
    except Exception:  # noqa: BLE001 — reported, never fatal
        logger.opt(exception=True).warning("Could not rotate the session after an admin invitation was accepted")
    return SuccessResponse[dict](data={"subRole": sub_role.value})
