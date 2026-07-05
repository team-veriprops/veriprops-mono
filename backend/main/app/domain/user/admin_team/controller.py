"""Admin team management controller (PRD §4.1). URL shape: /users/admins/team/..."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.user.admin_team.models import AdminTeamPageDto, ChangeSubRoleDto
from main.app.domain.user.admin_team.service import AdminTeamService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

admin_team_router = APIRouter(prefix="/admins/team", tags=["Admin Team"])
team_service: AdminTeamService = di[AdminTeamService]


@admin_team_router.get("", response_model=SuccessResponse[AdminTeamPageDto])
async def list_team(
    query: Optional[str] = Query(default=None),
    sub_role: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    result = await team_service.list_team(
        page=page, page_size=page_size, query=query, sub_role=sub_role,
    )
    return SuccessResponse[AdminTeamPageDto](data=result)


@admin_team_router.post("/{user_id}/sub-role", response_model=SuccessResponse[bool])
async def change_sub_role(
    user_id: str,
    req: ChangeSubRoleDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await team_service.change_sub_role(user_id, req.sub_role, admin_id)
    return SuccessResponse[bool](data=True)


@admin_team_router.post("/{user_id}/deactivate", response_model=SuccessResponse[bool])
async def deactivate_member(
    user_id: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await team_service.deactivate(user_id, admin_id)
    return SuccessResponse[bool](data=True)
