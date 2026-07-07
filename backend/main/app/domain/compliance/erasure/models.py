"""Data-erasure request domain (PRD §18.1, §19.1 / §4.11).

An NDPA "right to erasure" request over a single data subject. The subject (or an
admin on their behalf) opens the request; an admin with MANAGE_COMPLIANCE reviews
it and — on approval — the irreversible pseudonymisation step scrubs the subject's
identifying PII to a stable opaque token while the audit/consent records are
retained (§4.11). Statuses follow ``ErasureRequestState``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String, Text

from main.app.core.state.status import ErasureRequestState
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


# ─── ORM ──────────────────────────────────────────────────────────

class DataErasureRequest(BaseEntity):
    __tablename__ = "data_erasure_requests"

    subject_user_id = Column(String(36), nullable=False, index=True)
    requested_by_user_id = Column(String(36), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default=ErasureRequestState.PENDING.value, index=True)
    sla_due_at = Column(UTCDateTime, nullable=True)

    # Admin review + execution trail.
    reviewed_by_user_id = Column(String(36), nullable=True)
    reviewed_at = Column(UTCDateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    executed_at = Column(UTCDateTime, nullable=True)
    pseudonym_token = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_data_erasure_requests_subject", "subject_user_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateDataErasureRequestDto(Object):
    subject_user_id: str
    requested_by_user_id: str
    reason: Optional[str] = None
    status: ErasureRequestState = ErasureRequestState.PENDING
    sla_due_at: Optional[datetime] = None


class UpdateDataErasureRequestDto(Object):
    # Datetimes (reviewed_at/executed_at) are set on the attached row, never through
    # the update path (the DTO json-encoder would stringify them — see backend/CLAUDE.md).
    status: Optional[str] = None
    reviewed_by_user_id: Optional[str] = None
    decision_note: Optional[str] = None
    pseudonym_token: Optional[str] = None


class QueryDataErasureRequestDto(BaseQueryDto):
    subject_user_id: Optional[str] = None
    status: Optional[str] = None


class SearchDataErasureRequestDto(PageRequest, BaseQueryDto):
    status: Optional[str] = None


class RequestErasureDto(Object):
    """Self-service request body (Account → Data & privacy)."""
    reason: Optional[str] = None


class ResolveErasureDto(Object):
    """Admin reject/execute note."""
    note: Optional[str] = None


class DataErasureRequestDto(Object):
    id: str
    subject_user_id: str
    requested_by_user_id: str
    reason: Optional[str] = None
    status: ErasureRequestState
    sla_due_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    executed_at: Optional[datetime] = None
    date_created: datetime


def erasure_to_dto(r: "DataErasureRequest") -> DataErasureRequestDto:
    """Map a DataErasureRequest ORM row to its API DTO (shared by service + controller)."""
    return DataErasureRequestDto(
        id=r.id,
        subject_user_id=r.subject_user_id,
        requested_by_user_id=r.requested_by_user_id,
        reason=r.reason,
        status=ErasureRequestState(r.status),
        sla_due_at=r.sla_due_at,
        reviewed_at=r.reviewed_at,
        decision_note=r.decision_note,
        executed_at=r.executed_at,
        date_created=r.date_created,
    )
