"""Admin invitation service (PRD §4.1, decision-log D10)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.admin_invitation.models import (
    AdminInvitation,
    AdminInvitationIssuedDto,
    AdminInvitationStatus,
    AdminInvitationSummaryDto,
    CreateAdminInvitationDto,
    InviteAcceptScenario,
    InvitePreviewDto,
)
from main.app.domain.user.admin_invitation.repo import AdminInvitationRepo
from main.app.domain.user.models import AdminSubRole, UpdateUserDto
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.service import UserService
from main.app.domain.user.user_messages import AccountSecurityMessages
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidResourceStateException,
    InvalidTokenException,
    ResourceNotFoundException,
)
from main.appodus_utils.exception.faults import log_fault_once
from main.appodus_utils.integrations.messaging.models import MessageContext, MessageRequestRecipient
from main.appodus_utils.integrations.messaging.service import dispatch_delivered

@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminInvitationService:
    def __init__(
        self,
        invitation_repo: AdminInvitationRepo,
        user_service: UserService,
        audit_service: AuditLogService,
        account_security_messages: AccountSecurityMessages,
    ):
        self._invitation_repo = invitation_repo
        self._user_service = user_service
        self._audit_service = audit_service
        self._account_security_messages = account_security_messages

    async def invite(
        self,
        email: str,
        sub_role: AdminSubRole,
        invited_by: str,
        link_base: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AdminInvitationIssuedDto:
        """Create an invitation and email its link to the invitee.

        *link_base* is the origin the Super Admin is working on, so the link opens the same
        deployment. The link is returned either way, with whether the email went out.
        """
        raw_token = Utils.random_str(36)
        token_hash = Utils.sha256(raw_token)
        expires_at = Utils.datetime_now() + timedelta(hours=settings.ADMIN_INVITE_TTL_HOURS)
        invitation = await self._invitation_repo.create_return_model(CreateAdminInvitationDto(
            email=email,
            email_normalized=email.strip().lower(),
            first_name=first_name,
            last_name=last_name,
            sub_role=sub_role,
            token_hash=token_hash,
            invited_by=invited_by,
            expires_at=expires_at,
        ))
        self._audit_service.schedule(
            action=AuditActionType.ADMIN_INVITED,
            resource_type="admin_invitation",
            resource_id=invitation.id,
            actor_id=invited_by,
            details={"email": email, "sub_role": sub_role.value},
            ip_address=ip_address,
        )
        invite_url = f"{link_base}/auth/admin-invite/{raw_token}"
        email_sent = await self._email_invitation(
            email=email, first_name=first_name, last_name=last_name, sub_role=sub_role,
            invited_by=invited_by, invite_url=invite_url, expires_at=expires_at,
        )
        return AdminInvitationIssuedDto(invite_url=invite_url, email_sent=email_sent)

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

        # Claimed before anyone is elevated: an invitation revoked (or accepted) a moment ago
        # is no longer PENDING, so this request elevates no one.
        claimed = await self._invitation_repo.claim_transition(
            invitation.id, [AdminInvitationStatus.PENDING], AdminInvitationStatus.ACCEPTED,
            accepted_by=current_user_id, accepted_at=Utils.datetime_now(),
        )
        if claimed is None:
            raise InvalidTokenException(message="This invitation is no longer valid.")

        sub_role = AdminSubRole(invitation.sub_role)
        from_type = user.user_type
        await self._user_service.update_user(current_user_id, UpdateUserDto(
            user_type=UserType.ADMIN.value,
            admin_sub_role=sub_role.value,
        ))

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
        """Withdraw a pending invitation. Revoking twice is harmless; an invitation already
        accepted cannot be revoked — the invitee is an admin, and demotion is its own action."""
        invitation = await self._invitation_repo.get_model(invitation_id)
        if not invitation:
            raise ResourceNotFoundException(resource="admin invitation")
        claimed = await self._invitation_repo.claim_transition(
            invitation.id, [AdminInvitationStatus.PENDING], AdminInvitationStatus.REVOKED,
        )
        if claimed is not None:
            return
        current = await self._invitation_repo.get_model(invitation_id)
        if current is not None and current.status != AdminInvitationStatus.REVOKED.value:
            raise InvalidResourceStateException(
                resource="admin invitation", message="This invitation has already been accepted.",
            )

    # ── helpers ───────────────────────────────────────────────────
    async def _email_invitation(
        self,
        email: str,
        first_name: Optional[str],
        last_name: Optional[str],
        sub_role: AdminSubRole,
        invited_by: str,
        invite_url: str,
        expires_at: datetime,
    ) -> bool:
        """Email the invitee their link; True only when a channel reported it sent.

        Best-effort: the invitation already exists and its link goes back to the Super Admin,
        so a failed send means "pass it on by hand", never a failed invitation. Delivery
        retries stop when the invitation expires, since the link dies with it.
        """
        try:
            inviter = await self._user_service.get_user_model(invited_by)
            inviter_name = f"{inviter.first_name} {inviter.last_name}".strip()
            invitee_name = " ".join(filter(None, [first_name, last_name])) or None
            result = await self._account_security_messages.send_direct_admin_user_invite_message(
                recipient=MessageRequestRecipient(email=email, fullname=invitee_name),
                context={
                    MessageContext.FIRST_NAME: first_name,
                    MessageContext.LAST_NAME: last_name,
                    MessageContext.FULL_NAME: invitee_name,
                    MessageContext.INVITER_NAME: inviter_name,
                    MessageContext.ADMIN_ROLE: sub_role.value.replace("_", " ").title(),
                    MessageContext.LINK: invite_url,
                    MessageContext.VALIDITY: f"{settings.ADMIN_INVITE_TTL_HOURS} hours",
                },
                expires_at=expires_at,
            )
            return dispatch_delivered(result)
        except Exception as exc:  # noqa: BLE001 — reported, never fatal
            log_fault_once(exc, "admin invitation email")
            return False

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
