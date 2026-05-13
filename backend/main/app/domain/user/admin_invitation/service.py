"""Admin invitation service.

Owns invite creation, acceptance branching, and revocation. Email delivery is
best-effort; the invitation record is the source of truth.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import secrets
from datetime import timedelta
from typing import Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.user.admin_invitation.models import (
    AcceptInviteResultDto,
    AdminInvitation,
    AdminInvitationStatus,
    CreateAdminInvitationDto,
    InviteAdminResultDto,
    UpdateAdminInvitationDto,
)
from main.app.domain.user.admin_invitation.repo import AdminInvitationRepo
from main.app.domain.user.auth.session.models import SecurityEventType
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import AdminSubRole, UpdateUserDto, User
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

logger: Logger = di["logger"]


# Branch identifiers returned to the frontend at /accept.
BRANCH_SIGNUP_REQUIRED = "SIGNUP_REQUIRED"
BRANCH_LOGIN_REQUIRED = "LOGIN_REQUIRED"
BRANCH_ALREADY_ADMIN = "ALREADY_ADMIN"
BRANCH_ACCEPTED = "ACCEPTED"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminInvitationService:
    def __init__(
        self,
        repo: AdminInvitationRepo,
        user_repo: UserRepo,
        session_service: SessionService,
    ):
        self._repo = repo
        self._user_repo = user_repo
        self._session_service = session_service

    async def invite(
        self,
        inviter_admin_id: str,
        email: str,
        sub_role: AdminSubRole,
        first_name: str = "",
        last_name: str = "",
    ) -> InviteAdminResultDto:
        normalised_email = email.strip().lower()
        # Revoke any earlier pending invitation for the same email.
        existing = await self._repo.get_pending_for_email(email)
        if existing:
            await self._repo.update(str(existing.id), UpdateAdminInvitationDto(
                status=AdminInvitationStatus.REVOKED,
            ))

        raw_token = secrets.token_urlsafe(48)
        token_hash = Utils.sha256(raw_token)
        ttl_hours = settings.ADMIN_INVITE_TTL_HOURS or 72
        expires_at = Utils.datetime_now_plus(hours=ttl_hours)

        await self._repo.create(CreateAdminInvitationDto(
            email=email,
            email_normalized=normalised_email,
            first_name=first_name or None,
            last_name=last_name or None,
            sub_role=sub_role,
            inviter_admin_id=inviter_admin_id,
            token_hash=token_hash,
            expires_at=expires_at,
        ))
        row = await self._repo.get_by_token_hash(token_hash)
        if row is None:
            raise InvalidResourceStateException(
                resource="AdminInvitation",
                message="Invitation could not be created",
            )

        await self._record_event(
            type_=SecurityEventType.ADMIN_INVITED,
            description=f"invited {normalised_email} as {sub_role.value} by {inviter_admin_id}",
            user_id=inviter_admin_id,
        )

        inviter = await self._user_repo.get_model(inviter_admin_id)
        inviter_fullname = (
            f"{inviter.first_name or ''} {inviter.last_name or ''}".strip()
            if inviter else ""
        )

        return InviteAdminResultDto(
            invitation=await self._repo.to_query_dto(row),
            raw_token=raw_token,
            inviter_fullname=inviter_fullname,
        )

    async def get_pending_for_email(self, email: str) -> Optional[AdminInvitation]:
        return await self._repo.get_pending_for_email(email=email)

    async def list(self, status: Optional[AdminInvitationStatus] = None):
        from main.app.domain.user.admin_invitation.models import SearchAdminInvitationDto
        search = SearchAdminInvitationDto(page=0, page_size=100)
        if status:
            search.status = status.value
        page = await self._repo.get_page(search)
        return page

    async def revoke(self, invitation_id: str, admin_id: str) -> None:
        row = await self._repo.get_model(invitation_id)
        if row is None:
            raise ResourceNotFoundException(resource="AdminInvitation")
        if row.status != AdminInvitationStatus.PENDING.value:
            raise InvalidResourceStateException(
                resource="AdminInvitation",
                message="Only pending invitations can be revoked",
            )
        await self._repo.update(invitation_id, UpdateAdminInvitationDto(
            status=AdminInvitationStatus.REVOKED,
        ))
        await self._record_event(
            type_=SecurityEventType.ADMIN_ROLE_CHANGED,
            description=f"revoked invitation {invitation_id}",
            user_id=admin_id,
        )

    async def accept(
        self,
        raw_token: str,
        current_user_id: Optional[str] = None,
    ) -> AcceptInviteResultDto:
        if not raw_token:
            raise ValidationException(message="Invitation token required")
        token_hash = Utils.sha256(raw_token)
        invite = await self._repo.get_by_token_hash(token_hash)
        if invite is None or invite.status != AdminInvitationStatus.PENDING.value:
            raise ResourceNotFoundException(
                resource="AdminInvitation",
                message="Invitation is no longer valid",
            )
        if invite.expires_at <= Utils.datetime_now():
            await self._repo.update(str(invite.id), UpdateAdminInvitationDto(
                status=AdminInvitationStatus.EXPIRED,
            ))
            raise InvalidResourceStateException(
                resource="AdminInvitation",
                message="Invitation expired",
            )

        existing_user = await self._user_repo.get_by_email(invite.email_normalized)

        # Branch 1: no account
        if existing_user is None:
            return AcceptInviteResultDto(
                branch=BRANCH_SIGNUP_REQUIRED,
                email=invite.email,
                sub_role=AdminSubRole(invite.sub_role),
                first_name=invite.first_name,
                last_name=invite.last_name,
            )

        # Branch 3: already an admin
        if (existing_user.user_type or "").upper() == UserType.ADMIN.value:
            await self._repo.update(str(invite.id), UpdateAdminInvitationDto(
                status=AdminInvitationStatus.EXPIRED,
                accepted_by_user_id=str(existing_user.id),
            ))
            return AcceptInviteResultDto(
                branch=BRANCH_ALREADY_ADMIN,
                email=invite.email,
                first_name=invite.first_name,
                last_name=invite.last_name,
            )

        # Branch 2: existing non-admin user must be signed-in to merge.
        if not current_user_id:
            return AcceptInviteResultDto(
                branch=BRANCH_LOGIN_REQUIRED,
                email=invite.email,
                first_name=invite.first_name,
                last_name=invite.last_name,
            )
        if str(existing_user.id) != current_user_id:
            raise ValidationException(
                message="You must accept the invitation while signed in as the invited email",
            )

        await self._commit_acceptance(
            invite_id=str(invite.id),
            user_id=str(existing_user.id),
            admin_sub_role=invite.sub_role
        )
        return AcceptInviteResultDto(
            branch=BRANCH_ACCEPTED,
            email=invite.email,
            sub_role=AdminSubRole(invite.sub_role),
            first_name=invite.first_name,
            last_name=invite.last_name,
        )

    async def _commit_acceptance(
            self,
            invite_id: str,
            user_id: str,
            admin_sub_role: AdminSubRole,
    ) -> Optional[User]:
        user = await self._user_repo.update_return_model(user_id, UpdateUserDto(
            user_type=UserType.ADMIN.value,
            admin_sub_role=admin_sub_role,
        ))
        await self._repo.update(invite_id, UpdateAdminInvitationDto(
            status=AdminInvitationStatus.ACCEPTED,
            accepted_at=Utils.datetime_now(),
            accepted_by_user_id=user_id,
        ))
        await self._record_event(
            type_=SecurityEventType.ADMIN_INVITE_ACCEPTED,
            description=f"accepted invitation {invite_id}",
            user_id=user_id,
        )

        return user

    async def attach_admin_role_to_new_user(
        self,
        raw_token: str,
        user_id: str,
    ) -> None:
        """Called by signup flow when an invite token is supplied."""
        token_hash = Utils.sha256(raw_token)
        invite = await self._repo.get_by_token_hash(token_hash)
        if invite is None or invite.status != AdminInvitationStatus.PENDING.value:
            return
        if invite.expires_at <= Utils.datetime_now():
            return
        await self._user_repo.update(user_id, UpdateUserDto(
            user_type=UserType.ADMIN.value,
            admin_sub_role=invite.sub_role,
        ))
        await self._repo.update(str(invite.id), UpdateAdminInvitationDto(
            status=AdminInvitationStatus.ACCEPTED,
            accepted_at=Utils.datetime_now(),
            accepted_by_user_id=user_id,
        ))
        await self._record_event(
            type_=SecurityEventType.ADMIN_INVITE_ACCEPTED,
            description=f"accepted invitation {invite.id} via signup",
            user_id=user_id,
        )

    # ── Helpers ──
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
            logger.warning("Could not record admin invitation security event", exc_info=True)
