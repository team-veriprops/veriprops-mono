"""Admin user-management DTOs (PRD §4.2).

No new table — this domain administers the existing ``User`` entity: the all-users
directory, per-user detail, and the account actions (suspend / reactivate / forced
password reset / trust-status override).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import Field

from main.app.domain.user.auth.session.models import SecurityEventDto, UserPersona, UserType
from main.app.domain.user.models import AccountStatus, AdminSubRole, TrustStatus
from main.appodus_utils import Object


class AdminUserSummaryDto(Object):
    id: str
    name: str
    email: str
    email_verified: bool
    phone: str
    phone_dial_code: str
    user_type: UserType
    personas: List[UserPersona]
    admin_sub_role: Optional[AdminSubRole] = None
    trust_status: TrustStatus
    account_status: AccountStatus
    avatar_url: Optional[str] = None
    date_created: datetime


class AdminUserDetailDto(AdminUserSummaryDto):
    first_name: str
    last_name: str
    phone_country_code: str
    phone_verified: bool
    country_of_residence: str
    timezone: str
    preferred_currency: str
    credit_balance_kobo: int
    referred_by: Optional[str] = None
    locked_until: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    suspension_reason: Optional[str] = None
    suspended_by: Optional[str] = None
    verification_counts: Dict[str, int]
    verifications_total: int
    payments_count: int
    recent_security_events: List[SecurityEventDto]


class SuspendUserDto(Object):
    # The reason is admin-internal (audit + directory display) — never shown to the user.
    reason: str = Field(min_length=5, max_length=500)


class SetTrustStatusDto(Object):
    trust_status: TrustStatus


class ForcedPasswordResetDto(Object):
    """Internal hand-off from service to controller (raw reset token for email
    delivery) — never serialize this to the wire."""

    raw_token: str
    email: str
    full_name: str
