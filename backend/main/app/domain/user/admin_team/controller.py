"""Admin team HTTP routes — PRD §4.1 (R4.5).

URL shape: /users/admin/team/...
All endpoints require INVITE_ADMIN permission (SUPER admin only).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import List, Optional

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.user.admin_team.models import AdminTeamMemberDto, ChangeSubRoleRequestDto
from main.app.domain.user.admin_team.service import AdminTeamService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.user.models import AdminSubRole
from main.appodus_utils.db.models import SuccessResponse

logger: Logger = di["logger"]

admin_team_service: AdminTeamService = di[AdminTeamService]

admin_team_router = APIRouter(prefix="/admin/team", tags=["Admin Team"])


@admin_team_router.get(
    "",
    response_model=List[AdminTeamMemberDto],
)
async def list_team(
    sub_role: Optional[AdminSubRole] = None,
    _: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    return await admin_team_service.list_admins(sub_role_filter=sub_role)


@admin_team_router.post(
    "/{user_id}/deactivate",
    response_model=SuccessResponse[bool],
)
async def deactivate_admin(
    user_id: str,
    actor_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    await admin_team_service.deactivate_admin(actor_id=actor_id, target_id=user_id)
    return SuccessResponse[bool](data=True)


@admin_team_router.patch(
    "/{user_id}/sub-role",
    response_model=SuccessResponse[AdminTeamMemberDto],
)
async def change_sub_role(
    user_id: str,
    req: ChangeSubRoleRequestDto,
    actor_id: str = Depends(require_permission(Permission.INVITE_ADMIN)),
):
    result = await admin_team_service.change_sub_role(
        actor_id=actor_id,
        target_id=user_id,
        new_sub_role=req.sub_role,
    )
    return SuccessResponse[AdminTeamMemberDto](data=result)
