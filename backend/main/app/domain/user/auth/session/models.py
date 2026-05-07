"""Session & security audit models."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List

from pydantic import EmailStr
from sqlalchemy import Boolean, Column, DateTime, Index, String

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest

class UserType(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserPersona(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"

class SecurityEventType(str, enum.Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGIN_FAILURE_WARNING = "LOGIN_FAILURE_WARNING"
    OTP_SENT = "OTP_SENT"
    OTP_FAILURE = "OTP_FAILURE"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    SESSION_REVOKED = "SESSION_REVOKED"
    OAUTH_LINKED = "OAUTH_LINKED"
    OAUTH_UNLINKED = "OAUTH_UNLINKED"
    AGENT_APPLICATION_SUBMITTED = "AGENT_APPLICATION_SUBMITTED"
    AGENT_APPLICATION_APPROVED = "AGENT_APPLICATION_APPROVED"
    AGENT_APPLICATION_REJECTED = "AGENT_APPLICATION_REJECTED"
    ADMIN_INVITED = "ADMIN_INVITED"
    ADMIN_INVITE_ACCEPTED = "ADMIN_INVITE_ACCEPTED"
    ADMIN_ROLE_CHANGED = "ADMIN_ROLE_CHANGED"
    ADMIN_DEACTIVATED = "ADMIN_DEACTIVATED"
    TRUST_ELEVATED = "TRUST_ELEVATED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    VERIFICATION_SUBMITTED = "VERIFICATION_SUBMITTED"
    VERIFICATION_PAID = "VERIFICATION_PAID"


class DeviceSession(BaseEntity):
    __tablename__ = "device_sessions"

    user_id = Column(String(36), nullable=False, index=True)
    refresh_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    device = Column(String(512), nullable=False)
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)
    ip_address = Column(String(64), nullable=True)
    approx_location = Column(String(128), nullable=True)
    device_fingerprint = Column(String(128), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class SecurityEvent(BaseEntity):
    __tablename__ = "security_events"

    user_id = Column(String(36), nullable=True, index=True)
    type = Column(String(32), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    ip_address = Column(String(64), nullable=True)
    approx_location = Column(String(128), nullable=True)
    device = Column(String(512), nullable=True)
    device_fingerprint = Column(String(128), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)


class PasswordResetToken(BaseEntity):
    __tablename__ = "password_reset_tokens"

    user_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_password_reset_user", "user_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateDeviceSessionDto(Object):
    user_id: str
    refresh_token_hash: str
    device: str
    browser: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    device_fingerprint: Optional[str] = None
    last_active_at: datetime


class UpdateDeviceSessionDto(Object):
    last_active_at: Optional[datetime] = None
    revoked: Optional[bool] = None
    revoked_at: Optional[datetime] = None


class SearchDeviceSessionDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    revoked: Optional[bool] = None


class QueryDeviceSessionDto(BaseQueryDto):
    user_id: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    last_active_at: Optional[datetime] = None
    revoked: Optional[bool] = None



class DeviceSessionDto(Object):
    id: str
    device: str
    browser: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    current: bool
    last_active_at: datetime
    created_at: datetime


class CreateSecurityEventDto(Object):
    user_id: Optional[str] = None
    type: SecurityEventType
    description: str
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    device: Optional[str] = None
    device_fingerprint: Optional[str] = None
    occurred_at: datetime


class UpdateSecurityEventDto(Object):
    pass


class SearchSecurityEventDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    type: Optional[str] = None


class QuerySecurityEventDto(BaseQueryDto):
    user_id: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    device: Optional[str] = None
    occurred_at: Optional[datetime] = None


class SecurityEventDto(Object):
    id: str
    type: str
    description: str
    ip_address: Optional[str] = None
    approx_location: Optional[str] = None
    device: Optional[str] = None
    occurred_at: datetime


class CreatePasswordResetTokenDto(Object):
    user_id: str
    token_hash: str
    expires_at: datetime


class UpdatePasswordResetTokenDto(Object):
    consumed_at: Optional[datetime] = None


class SearchPasswordResetTokenDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    token_hash: Optional[str] = None


class QueryPasswordResetTokenDto(BaseQueryDto):
    user_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None


# User Session

class LoginRequestDto(Object):
    email: EmailStr
    password: str
    device_fingerprint: Optional[str] = None

class AuthSessionDto(Object):
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    user: SessionUserDto


class SessionUserDto(Object):
    id: str
    first_name: str
    last_name: str
    email: str
    email_verified: bool
    phone: str
    phone_country_code: str
    phone_dial_code: str
    phone_verified: bool
    country_of_residence: str
    timezone: str
    preferred_currency: str
    user_type: UserType
    personas: List[UserPersona]
    admin_sub_role: Optional[str] = None
    trust_status: str
    has_password: bool
    linked_providers: List[SocialAuthProvider]
    avatar_url: Optional[str] = None
    created_at: datetime
