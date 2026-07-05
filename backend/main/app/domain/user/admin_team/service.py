"""Admin team management service (PRD §4.1): list, deactivate, change sub-role."""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.admin_team.models import AdminMemberDto, AdminTeamPageDto
from main.app.domain.user.models import AdminSubRole, UpdateUserDto
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.service import UserService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminTeamService:
    def __init__(
        self,
        user_repo: UserRepo,
        user_service: UserService,
        audit_service: AuditLogService,
    ):
        self._user_repo = user_repo
        self._user_service = user_service
        self._audit_service = audit_service

    async def list_team(
        self,
        page: int = 0,
        page_size: int = 10,
        query: Optional[str] = None,
        sub_role: Optional[str] = None,
    ) -> AdminTeamPageDto:
        sub_role_filter = AdminSubRole(sub_role) if sub_role else None
        admins = await self._user_repo.list_admins(sub_role_filter=sub_role_filter, query=query)
        total = len(admins)
        start = page * page_size
        window = admins[start:start + page_size]
        items = [
            AdminMemberDto(
                id=u.id,
                name=f"{u.first_name} {u.last_name}".strip(),
                email=u.email,
                sub_role=AdminSubRole(u.admin_sub_role) if u.admin_sub_role else None,
                active=not u.deleted,
                date_created=u.date_created,
            )
            for u in window
        ]
        return AdminTeamPageDto(items=items, total=total, page=page, page_size=page_size)

    async def change_sub_role(self, user_id: str, sub_role: AdminSubRole, admin_id: str) -> None:
        user = await self._user_service.get_user_model(user_id)
        self._assert_is_admin(user)
        from_role = user.admin_sub_role
        await self._user_repo.update(user_id, UpdateUserDto(admin_sub_role=sub_role.value))
        self._audit_service.schedule(
            action=AuditActionType.ADMIN_ROLE_CHANGED,
            resource_type="user",
            resource_id=user_id,
            actor_id=admin_id,
            from_state=from_role,
            to_state=sub_role.value,
        )

    async def deactivate(self, user_id: str, admin_id: str) -> None:
        """Remove admin access (demote to a plain USER). PRD §4.1 team management."""
        user = await self._user_service.get_user_model(user_id)
        self._assert_is_admin(user)
        if user_id == admin_id:
            raise ValidationException(message="You cannot deactivate your own admin access.")
        from_role = user.admin_sub_role
        await self._user_repo.demote_to_user(user_id)
        self._audit_service.schedule(
            action=AuditActionType.ADMIN_ROLE_CHANGED,
            resource_type="user",
            resource_id=user_id,
            actor_id=admin_id,
            from_state=from_role,
            to_state="DEACTIVATED",
        )

    def _assert_is_admin(self, user) -> None:
        from main.app.domain.user.auth.session.models import UserType
        if not user or user.user_type != UserType.ADMIN.value:
            raise ResourceNotFoundException(resource="admin team member")
