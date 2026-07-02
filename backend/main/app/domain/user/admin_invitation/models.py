"""Admin invitation domain models (PRD §4.1).

A Super Admin invites a new admin with a sub-role via a tokenised link (72-hour
validity). Acceptance elevates the accepting user to ADMIN (see decision-log D10).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import EmailStr
from sqlalchemy import Column, Index, String

from main.app.domain.user.models import AdminSubRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class AdminInvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"


class InviteAcceptScenario(str, enum.Enum):
    """How the invitee should proceed (PRD §4.1 three scenarios)."""

    NEW_USER = "NEW_USER"          # no account → pre-filled signup then accept
    EXISTING_USER = "EXISTING_USER"  # has a USER account → log in to merge admin
    ALREADY_ADMIN = "ALREADY_ADMIN"  # already an admin → friendly no-op


class AdminInvitation(BaseEntity):
    __tablename__ = "admin_invitations"

    email = Column(String(254), nullable=False, index=True)
    email_normalized = Column(String(254), nullable=False, index=True)
    sub_role = Column(String(16), nullable=False)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default=AdminInvitationStatus.PENDING.value)
    invited_by = Column(String(36), nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)
    accepted_at = Column(UTCDateTime, nullable=True)
    accepted_by = Column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_admin_invitations_email_norm", "email_normalized"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAdminInvitationDto(Object):
    email: str
    email_normalized: str
    sub_role: AdminSubRole
    token_hash: str
    invited_by: str
    expires_at: datetime
    status: AdminInvitationStatus = AdminInvitationStatus.PENDING


class UpdateAdminInvitationDto(Object):
    status: Optional[str] = None
    accepted_by: Optional[str] = None


class SearchAdminInvitationDto(PageRequest, BaseQueryDto):
    email: Optional[str] = None
    status: Optional[str] = None


class QueryAdminInvitationDto(BaseQueryDto):
    email: Optional[str] = None
    sub_role: Optional[str] = None
    status: Optional[str] = None
    invited_by: Optional[str] = None
    expires_at: Optional[datetime] = None


# ─── API request/response DTOs ────────────────────────────────────

class InviteAdminRequestDto(Object):
    email: EmailStr
    sub_role: AdminSubRole


class AdminInvitationSummaryDto(Object):
    id: str
    email: str
    sub_role: AdminSubRole
    status: AdminInvitationStatus
    invited_by: str
    expires_at: datetime
    date_created: datetime


class InvitePreviewDto(Object):
    """Unauthenticated preview so the frontend can route the acceptance flow."""

    email: str
    sub_role: AdminSubRole
    status: AdminInvitationStatus
    expired: bool
    scenario: InviteAcceptScenario
