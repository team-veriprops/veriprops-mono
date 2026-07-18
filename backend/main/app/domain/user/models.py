"""User & OAuth identity domain models. PRD §2 (Actors & Role Architecture)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr, Field
from sqlalchemy import BigInteger, Boolean, Column, String, Integer
from sqlalchemy.ext.mutable import MutableList

from main.app.domain.user.auth.session.models import UserType, UserPersona
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime, jsonb_variant
from main.appodus_utils.db.types.money import TransactionCurrency


class AdminSubRole(str, enum.Enum):
    SUPER = "SUPER"
    OPERATIONS = "OPERATIONS"
    FINANCE = "FINANCE"
    CONTENT_CREATOR = "CONTENT_CREATOR"
    CONTENT_APPROVER = "CONTENT_APPROVER"


class TrustStatus(str, enum.Enum):
    UNTRUSTED = "UNTRUSTED"
    TRUSTED = "TRUSTED"


class AccountStatus(str, enum.Enum):
    """Whole-account availability, admin-controlled (distinct from the agent
    *role-level* credential suspension in §2.4 and the transient brute-force
    ``locked_until`` lockout). A SUSPENDED user cannot log in and has all
    device sessions revoked at suspension time."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


# ─── ORM ──────────────────────────────────────────────────────────

class User(BaseEntity):
    __tablename__ = "users"

    first_name = Column(String(60), nullable=False)
    last_name = Column(String(60), nullable=False)
    email = Column(String(254), nullable=False)
    email_normalized = Column(String(254), nullable=False, unique=True, index=True)
    email_verified = Column(Boolean, nullable=False, default=False)

    phone_country_code = Column(String(2), nullable=False)
    phone_dial_code = Column(String(8), nullable=False)
    phone = Column(String(32), nullable=False)
    phone_e164 = Column(String(32), nullable=True, index=True)
    phone_verified = Column(Boolean, nullable=False, default=False)

    country_of_residence = Column(String(2), nullable=False)
    timezone = Column(String(64), nullable=False)
    preferred_currency = Column(String(8), nullable=False, default="NGN")

    user_type = Column(String(8), nullable=False, default=UserType.USER.value)
    personas = Column(MutableList.as_mutable(jsonb_variant()), nullable=False, default=list)
    admin_sub_role = Column(String(16), nullable=True)

    trust_status = Column(String(16), nullable=False, default=TrustStatus.UNTRUSTED.value)

    # Admin-controlled whole-account availability (§2.4a). Suspension metadata is
    # kept on the row so the admin directory can show who/why/when without a join.
    account_status = Column(String(16), nullable=False, default=AccountStatus.ACTIVE.value,
                            server_default=AccountStatus.ACTIVE.value)
    suspended_at = Column(UTCDateTime, nullable=True)
    suspension_reason = Column(String(500), nullable=True)
    # Admin user id (36-char str form), application-enforced reference.
    suspended_by = Column(String(36), nullable=True)

    # Phase 17 — referral credits (stored in kobo to avoid float precision issues)
    credit_balance_kobo = Column(BigInteger, nullable=False, default=0)
    # Phase 17 — the referrer this user signed up under (§17.1), user id (str form). Null = organic.
    referred_by = Column(String(36), nullable=True, index=True)

    password_hash = Column(String(255), nullable=True)  # nullable for OAuth-only users
    avatar_url = Column(String(512), nullable=True)
    locked_until = Column(UTCDateTime, nullable=True)
    failed_login_count = Column(Integer(), nullable=False, server_default="0")
    # phone_e164's index is declared inline (index=True) — it auto-names to
    # ix_users_phone_e164, matching the migration. Don't re-declare it here.

    # True once the customer has dirtied their first verification draft (§ auto-launch
    # the new-verification wizard on first login, never again after). Flipped in
    # VerificationService.create_draft's "create new" branch — never unset.
    has_started_verification = Column(Boolean, nullable=False, default=False, server_default="false")


# ─── DTOs ─────────────────────────────────────────────────────────

class UserBaseDto(Object):
    first_name: str
    last_name: str
    email: EmailStr
    phone_country_code: str
    phone_dial_code: str
    phone: str
    country_of_residence: str
    timezone: str
    preferred_currency: TransactionCurrency = TransactionCurrency.NGN


class CreateUserDto(UserBaseDto):
    password_hash: Optional[str] = None
    personas: List[UserPersona] = Field(default_factory=list)
    admin_sub_role: Optional[AdminSubRole] = None
    email_verified: bool = False
    phone_verified: bool = False
    referred_by: Optional[str] = None


class _CreateUserDto(CreateUserDto):
    user_type: UserType = UserType.USER
    phone_e164: str
    email_normalized: str


class UpdateUserDto(Object):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    email_verified: Optional[bool] = None
    phone_country_code: Optional[str] = None
    phone_dial_code: Optional[str] = None
    phone: Optional[str] = None
    phone_e164: Optional[str] = None
    phone_verified: Optional[bool] = None
    country_of_residence: Optional[str] = None
    timezone: Optional[str] = None
    preferred_currency: Optional[str] = None
    user_type: Optional[str] = None
    personas: Optional[List[str]] = None
    admin_sub_role: Optional[str] = None
    trust_status: Optional[str] = None
    credit_balance_kobo: Optional[int] = None
    referred_by: Optional[str] = None
    password_hash: Optional[str] = None
    avatar_url: Optional[str] = None
    locked_until: Optional[datetime] = None
    failed_login_count: Optional[int] = None
    has_started_verification: Optional[bool] = None


class SearchUserDto(InternalPageRequest, BaseQueryDto):
    email: Optional[str] = None
    phone_e164: Optional[str] = None
    user_type: Optional[str] = None


class QueryUserDto(BaseQueryDto):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    phone_country_code: Optional[str] = None
    phone_dial_code: Optional[str] = None
    phone: Optional[str] = None
    phone_verified: Optional[bool] = None
    country_of_residence: Optional[str] = None
    timezone: Optional[str] = None
    preferred_currency: Optional[str] = None
    user_type: Optional[str] = None
    personas: Optional[List[str]] = None
    admin_sub_role: Optional[str] = None
    trust_status: Optional[str] = None
    account_status: Optional[str] = None
    avatar_url: Optional[str] = None
