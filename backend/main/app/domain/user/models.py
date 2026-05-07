"""User & OAuth identity domain models. PRD §2 (Actors & Role Architecture)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr, Field
from sqlalchemy import Boolean, Column, DateTime, Index, String, Integer, JSON
from sqlalchemy.ext.mutable import MutableList

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.session.models import UserType, UserPersona
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.types.money import TransactionCurrency


class AdminSubRole(str, enum.Enum):
    SUPER = "SUPER"
    OPERATIONS = "OPERATIONS"
    FINANCE = "FINANCE"


class TrustStatus(str, enum.Enum):
    UNTRUSTED = "UNTRUSTED"
    TRUSTED = "TRUSTED"


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
    personas = Column(MutableList.as_mutable(JSON), nullable=False, default=list)
    admin_sub_role = Column(String(16), nullable=True)

    trust_status = Column(String(16), nullable=False, default=TrustStatus.UNTRUSTED.value)

    password_hash = Column(String(255), nullable=True)  # nullable for OAuth-only users
    avatar_url = Column(String(512), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    failed_login_count = Column(Integer(), nullable=False, server_default="0")

    __table_args__ = (
        Index("ix_users_phone_e164", "phone_e164"),
    )


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
    personas: List[UserPersona] = Field(default_factory=list)
    admin_sub_role: Optional[AdminSubRole] = None
    email_verified: bool = False
    phone_verified: bool = False


class _CreateUserDto(CreateUserDto):
    user_type: UserType = UserType.USER

    password_hash: Optional[str] = None
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
    personas: Optional[List[str]] = None
    admin_sub_role: Optional[str] = None
    trust_status: Optional[str] = None
    password_hash: Optional[str] = None
    avatar_url: Optional[str] = None
    locked_until: Optional[datetime] = None
    failed_login_count: Optional[int] = None


class SearchUserDto(PageRequest, BaseQueryDto):
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
    avatar_url: Optional[str] = None
