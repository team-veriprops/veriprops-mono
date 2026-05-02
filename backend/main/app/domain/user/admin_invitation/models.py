"""Admin invitation domain — PRD Phase 4 (Admin Onboarding & Role Management).

A Super Admin invites a new admin via tokenised email link. The raw token is
returned to the inviter once at creation; only its hash is stored. Acceptance
behaviour depends on whether the invitee already has an account (see service).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, Index, String

from main.app.domain.user.models import AdminSubRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class AdminInvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


# ─── ORM ──────────────────────────────────────────────────────────


class AdminInvitation(BaseEntity):
    __tablename__ = "admin_invitations"

    email_normalized = Column(String(254), nullable=False, index=True)
    sub_role = Column(String(16), nullable=False)
    inviter_admin_id = Column(String(36), nullable=False)
    token_hash = Column(String(128), nullable=False, unique=True)
    status = Column(String(16), nullable=False, default=AdminInvitationStatus.PENDING.value, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(String(36), nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────


class CreateAdminInvitationDto(Object):
    email_normalized: str
    sub_role: AdminSubRole
    inviter_admin_id: str
    token_hash: str
    status: AdminInvitationStatus = AdminInvitationStatus.PENDING
    expires_at: datetime


class UpdateAdminInvitationDto(Object):
    status: Optional[AdminInvitationStatus] = None
    accepted_at: Optional[datetime] = None
    accepted_by_user_id: Optional[str] = None


class SearchAdminInvitationDto(PageRequest, BaseQueryDto):
    email_normalized: Optional[str] = None
    status: Optional[str] = None


class QueryAdminInvitationDto(BaseQueryDto):
    email_normalized: Optional[str] = None
    status: Optional[str] = None
    sub_role: Optional[str] = None


# ── Inputs / outputs ──


class InviteAdminRequestDto(Object):
    email: EmailStr
    sub_role: AdminSubRole


class AcceptInviteRequestDto(Object):
    token: str


class AdminInvitationDto(Object):
    id: str
    email: str
    sub_role: AdminSubRole
    status: AdminInvitationStatus
    inviter_admin_id: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime


class InviteAdminResultDto(Object):
    invitation: AdminInvitationDto
    # Raw, single-use token returned to the inviter so they can copy/forward
    # the link if email delivery fails. Omitted on subsequent reads.
    raw_token: str


class AcceptInviteResultDto(Object):
    """Branch indicator for the frontend.

    - SIGNUP_REQUIRED: invitee has no account; redirect to signup pre-filled.
    - LOGIN_REQUIRED: invitee has an account; ask for login then re-call.
    - ALREADY_ADMIN: invitee is already an admin; show friendly page.
    - ACCEPTED: invitation was consumed and admin role attached.
    """
    branch: str
    email: str
    sub_role: Optional[AdminSubRole] = None
