"""Re-check domain (PRD §14.1)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import BigInteger, Column, Index, String, Text

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import JSONB_VARIANT


class RecheckStatus(str, enum.Enum):
    """Re-check request lifecycle. PENDING → APPROVED (awaiting payment) → STARTED (paid,
    scoped tasks reopened). Admin may REJECT a pending request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STARTED = "STARTED"


# ─── ORM ──────────────────────────────────────────────────────────

class RecheckRequest(BaseEntity):
    __tablename__ = "recheck_requests"

    verification_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    documents = Column(JSONB_VARIANT, nullable=True)      # optional supporting docs (refs)
    scope_roles = Column(JSONB_VARIANT, nullable=True)    # admin-set roles to reopen
    status = Column(String(16), nullable=False, default=RecheckStatus.PENDING.value, index=True)
    price_minor = Column(BigInteger, nullable=False, default=0)
    payment_id = Column(String(36), nullable=True, index=True)
    decision_note = Column(String(1000), nullable=True)

    __table_args__ = (
        Index("ix_recheck_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateRecheckDto(Object):
    verification_id: str
    customer_id: str
    reason: str
    documents: Optional[List[dict]] = None
    price_minor: int = 0
    status: RecheckStatus = RecheckStatus.PENDING


class UpdateRecheckDto(Object):
    status: Optional[str] = None
    scope_roles: Optional[List[str]] = None
    payment_id: Optional[str] = None
    decision_note: Optional[str] = None


class QueryRecheckDto(BaseQueryDto):
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None


class SearchRecheckDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    status: Optional[str] = None


class RequestRecheckDto(Object):
    reason: str
    documents: Optional[List[dict]] = None


class DecideRecheckDto(Object):
    approve: bool
    scope_roles: Optional[List[AgentRole]] = None
    note: Optional[str] = None


class RecheckDto(Object):
    id: str
    verification_id: str
    reason: str
    documents: Optional[List[Any]] = None
    scope_roles: Optional[List[str]] = None
    status: RecheckStatus
    price_minor: int
    payment_id: Optional[str] = None
    checkout_url: Optional[str] = None   # present for an APPROVED re-check awaiting payment
    decision_note: Optional[str] = None
    date_created: datetime
