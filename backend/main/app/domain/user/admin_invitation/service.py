"""Admin invitation service (PRD §4.1, decision-log D10)."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.admin_invitation.models import (
    AdminInvitation,
    AdminInvitationStatus,
    AdminInvitationSummaryDto,
    CreateAdminInvitationDto,
    InviteAcceptScenario,
    InvitePreviewDto,
    UpdateAdminInvitationDto,
)
from main.app.domain.user.admin_invitation.repo import AdminInvitationRepo
from main.app.domain.user.models import AdminSubRole, UpdateUserDto
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidTokenException,
    ResourceNotFoundException,
)

@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminInvitationService:
    def __init__(
        self,
        invitation_repo: AdminInvitationRepo,
        user_service: UserService,
        audit_service: AuditLogService,
    ):
        self._invitation_repo = invitation_repo
        self._user_service = user_service
        self._audit_service = audit_service

    async def invite(
        self,
        email: str,
        sub_role: AdminSubRole,
        invited_by: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Create an invitation; returns the raw token for the caller to email."""
        raw_token = Utils.random_str(36)
        token_hash = Utils.sha256(raw_token)
        invitation = await self._invitation_repo.create_return_model(CreateAdminInvitationDto(
            email=email,
            email_normalized=email.strip().lower(),
            first_name=first_name,
            last_name=last_name,
            sub_role=sub_role,
            token_hash=token_hash,
            invited_by=invited_by,
            expires_at=Utils.datetime_now() + timedelta(hours=settings.ADMIN_INVITE_TTL_HOURS),
        ))
        self._audit_service.schedule(
            action=AuditActionType.ADMIN_INVITED,
            resource_type="admin_invitation",
            resource_id=invitation.id,
            actor_id=invited_by,
            details={"email": email, "sub_role": sub_role.value},
            ip_address=ip_address,
        )
        return raw_token

    async def preview(self, raw_token: str) -> InvitePreviewDto:
        invitation = await self._require_invitation(raw_token)
        expired = invitation.expires_at < Utils.datetime_now()
        existing = await self._user_service.get_user_by_email(invitation.email)
        if existing and existing.user_type == UserType.ADMIN.value:
            scenario = InviteAcceptScenario.ALREADY_ADMIN
        elif existing:
            scenario = InviteAcceptScenario.EXISTING_USER
        else:
            scenario = InviteAcceptScenario.NEW_USER
        return InvitePreviewDto(
            email=invitation.email,
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            sub_role=AdminSubRole(invitation.sub_role),
            status=AdminInvitationStatus(invitation.status),
            expired=expired,
            scenario=scenario,
        )

    async def accept(self, raw_token: str, current_user_id: str) -> AdminSubRole:
        """Elevate the authenticated user to ADMIN with the invited sub-role (D10)."""
        invitation = await self._require_invitation(raw_token)
        self._assert_acceptable(invitation)

        user = await self._user_service.get_user_model(current_user_id)
        # Prevent accepting an invitation addressed to someone else.
        if (user.email or "").strip().lower() != invitation.email_normalized:
            raise ForbiddenException(message="This invitation was issued for a different email.")

        sub_role = AdminSubRole(invitation.sub_role)
        from_type = user.user_type
        await self._user_service.update_user(current_user_id, UpdateUserDto(
            user_type=UserType.ADMIN.value,
            admin_sub_role=sub_role.value,
        ))
        await self._invitation_repo.update(invitation.id, UpdateAdminInvitationDto(
            status=AdminInvitationStatus.ACCEPTED.value,
            accepted_by=current_user_id,
        ))
        await self._mark_accepted_at(invitation.id)

        self._audit_service.schedule(
            action=AuditActionType.ADMIN_INVITE_ACCEPTED,
            resource_type="admin_invitation",
            resource_id=invitation.id,
            actor_id=current_user_id,
            from_state=from_type,
            to_state=UserType.ADMIN.value,
            details={"sub_role": sub_role.value},
        )
        return sub_role

    async def list_invitations(self, page: int = 0, page_size: int = 10) -> Page[AdminInvitationSummaryDto]:
        rows, total = await self._invitation_repo.page_all(offset=page * page_size, limit=page_size)
        items = [
            AdminInvitationSummaryDto(
                id=r.id,
                email=r.email,
                first_name=r.first_name,
                last_name=r.last_name,
                sub_role=AdminSubRole(r.sub_role),
                status=AdminInvitationStatus(r.status),
                invited_by=r.invited_by,
                expires_at=r.expires_at,
                date_created=r.date_created,
            )
            for r in rows
        ]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[AdminInvitationSummaryDto](
            items=items,
            meta=PaginationMeta(
                page=page, page_size=page_size, count=len(items), total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    async def revoke(self, invitation_id: str, admin_id: str) -> None:
        invitation = await self._invitation_repo.get_model(invitation_id)
        if not invitation:
            raise ResourceNotFoundException(resource="admin invitation")
        await self._invitation_repo.update(
            invitation_id, UpdateAdminInvitationDto(status=AdminInvitationStatus.REVOKED.value)
        )

    # ── helpers ───────────────────────────────────────────────────
    async def _require_invitation(self, raw_token: str) -> AdminInvitation:
        invitation = await self._invitation_repo.get_by_token_hash(Utils.sha256(raw_token))
        if not invitation:
            raise InvalidTokenException(message="Invalid invitation link.")
        return invitation

    def _assert_acceptable(self, invitation: AdminInvitation) -> None:
        if invitation.status != AdminInvitationStatus.PENDING.value:
            raise InvalidTokenException(message="This invitation is no longer valid.")
        if invitation.expires_at < Utils.datetime_now():
            raise InvalidTokenException(message="This invitation has expired.")

    async def _mark_accepted_at(self, invitation_id: str) -> None:
        invitation = await self._invitation_repo.get_model(invitation_id)
        invitation.accepted_at = Utils.datetime_now()
