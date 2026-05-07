"""Admin team management service — PRD §4.1 (R4.5).

Owns listing, deactivating, and sub-role reassignment for admin accounts.
All mutations emit a SecurityEvent for the audit trail.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import List, Optional

from kink import di, inject

from main.app.domain.user.admin_team.models import AdminTeamMemberDto
from main.app.domain.user.auth.session.models import SecurityEventType, UserType
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import AdminSubRole, UpdateUserDto
from main.app.domain.user.repo import UserRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

logger: Logger = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminTeamService:
    def __init__(self, user_repo: UserRepo, session_service: SessionService):
        self._user_repo = user_repo
        self._session_service = session_service

    async def list_admins(
        self, sub_role_filter: Optional[AdminSubRole] = None
    ) -> List[AdminTeamMemberDto]:
        admins = await self._user_repo.list_admins(sub_role_filter=sub_role_filter)
        return [self._to_dto(u) for u in admins]

    async def deactivate_admin(self, actor_id: str, target_id: str) -> None:
        if actor_id == target_id:
            raise ValidationException(message="Cannot deactivate your own admin account")

        target = await self._user_repo.get_model(target_id)
        if target is None or (target.user_type or "").upper() != UserType.ADMIN.value:
            raise ResourceNotFoundException(resource="Admin")

        if (target.admin_sub_role or "").upper() == AdminSubRole.SUPER.value:
            supers = await self._user_repo.list_admins(sub_role_filter=AdminSubRole.SUPER)
            if len(supers) <= 1:
                raise InvalidResourceStateException(
                    resource="Admin",
                    message="Cannot deactivate the last SUPER admin",
                )

        await self._user_repo.demote_to_user(target_id)
        await self._record_event(
            type_=SecurityEventType.ADMIN_DEACTIVATED,
            description=f"admin {target_id} deactivated by actor {actor_id}",
            user_id=actor_id,
        )

    async def change_sub_role(
        self, actor_id: str, target_id: str, new_sub_role: AdminSubRole
    ) -> AdminTeamMemberDto:
        target = await self._user_repo.get_model(target_id)
        if target is None or (target.user_type or "").upper() != UserType.ADMIN.value:
            raise ResourceNotFoundException(resource="Admin")

        old_role = target.admin_sub_role or "NONE"
        await self._user_repo.update(target_id, UpdateUserDto(admin_sub_role=new_sub_role.value))
        await self._record_event(
            type_=SecurityEventType.ADMIN_ROLE_CHANGED,
            description=f"admin {target_id} sub-role changed {old_role} → {new_sub_role.value} by {actor_id}",
            user_id=actor_id,
        )

        updated = await self._user_repo.get_model(target_id)
        return self._to_dto(updated)

    # ── Helpers ──

    @staticmethod
    def _to_dto(user) -> AdminTeamMemberDto:
        return AdminTeamMemberDto(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            sub_role=AdminSubRole(user.admin_sub_role),
            created_at=user.date_created,
        )

    async def _record_event(
        self, type_: SecurityEventType, description: str, user_id: Optional[str] = None,
    ) -> None:
        try:
            await self._session_service.record_event(
                type=type_,
                description=description[:255],
                user_id=user_id,
            )
        except Exception:  # pragma: no cover
            logger.warning("Could not record admin team security event", exc_info=True)
