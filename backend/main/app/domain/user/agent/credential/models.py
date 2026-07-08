"""Agent professional-credential domain (PRD §3.1 step 3, §3.3a).

A per-role licence (Surveyor, Lawyer) with a structured expiry. Expiry drives
role-level (not account-level) suspension — see ``rules.py``.
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Column, Date, String

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


class CredentialType(str, enum.Enum):
    """Professional credentials with a natural expiry (PRD §3.1 step 3, §3.3a)."""

    SURVEYOR_LICENCE = "SURVEYOR_LICENCE"
    NBA_LICENCE = "NBA_LICENCE"


class CredentialStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    # Set when the credential's expiry_date has passed — the role it backs is
    # suspended (role-level, not account-level, PRD §3.3a).
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


# The credential each role requires before it can be approved / stay active
# (PRD §3.1 step 3). Roles absent here need no professional licence.
ROLE_REQUIRED_CREDENTIAL = {
    AgentRole.SURVEYOR: CredentialType.SURVEYOR_LICENCE,
    AgentRole.LAWYER: CredentialType.NBA_LICENCE,
}


# ─── ORM ──────────────────────────────────────────────────────────

class AgentCredential(BaseEntity):
    __tablename__ = "agent_credentials"

    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    credential_type = Column(String(32), nullable=False)
    licence_number = Column(String(64), nullable=True)
    # Encrypted-S3 object key for the uploaded credential document (access-controlled).
    document_ref = Column(String(512), nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(16), nullable=False, default=CredentialStatus.PENDING.value)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAgentCredentialDto(Object):
    user_id: str
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    expiry_date: Optional[date] = None
    status: CredentialStatus = CredentialStatus.PENDING


class UpdateAgentCredentialDto(Object):
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    status: Optional[str] = None


class SearchAgentCredentialDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    role: Optional[str] = None


class QueryAgentCredentialDto(BaseQueryDto):
    user_id: Optional[str] = None
    role: Optional[str] = None
    credential_type: Optional[str] = None
    licence_number: Optional[str] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None


# ─── API request/response DTOs ────────────────────────────────────

class AgentCredentialInputDto(Object):
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    document_ref: Optional[str] = None
    expiry_date: Optional[date] = None


class AgentCredentialDto(Object):
    role: AgentRole
    credential_type: CredentialType
    licence_number: Optional[str] = None
    expiry_date: Optional[date] = None
    status: CredentialStatus
