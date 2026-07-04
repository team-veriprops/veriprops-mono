"""Verification report domain (PRD §2.3, §8.3, §8.6, §10).

The report is the released deliverable: a versioned, immutable snapshot of the
per-role findings plus the composite trust score, produced only by an explicit admin
release (§8 — no report without release). Re-release produces a **new version** and
supersedes the previous (§8.6). The report state machine is DRAFT → RELEASED → SUPERSEDED.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy import Index

from main.app.core.state.status import ReportState
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT


# ─── ORM ──────────────────────────────────────────────────────────

class Report(BaseEntity):
    __tablename__ = "reports"

    verification_id = Column(String(36), nullable=False, index=True)
    # Monotonic per-verification document version (NOT BaseEntity.version, which is the
    # optimistic-lock counter). A re-release increments this and supersedes the prior.
    report_version = Column(Integer, nullable=False, default=1)
    state = Column(String(16), nullable=False, default=ReportState.DRAFT.value, index=True)
    composite_trust_score = Column(Integer, nullable=True)
    # Immutable snapshot of the per-role submission findings at release time.
    findings = Column(JSONB_VARIANT, nullable=True)
    release_reason = Column(String(1000), nullable=True)
    released_by = Column(String(36), nullable=True)
    released_at = Column(UTCDateTime, nullable=True)
    superseded_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        Index("ix_reports_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateReportDto(Object):
    verification_id: str
    report_version: int = 1
    state: ReportState = ReportState.DRAFT
    composite_trust_score: Optional[int] = None
    findings: Optional[Dict[str, Any]] = None
    release_reason: Optional[str] = None
    released_by: Optional[str] = None


class UpdateReportDto(Object):
    state: Optional[str] = None
    composite_trust_score: Optional[int] = None
    findings: Optional[Dict[str, Any]] = None
    release_reason: Optional[str] = None


class QueryReportDto(BaseQueryDto):
    verification_id: Optional[str] = None
    state: Optional[str] = None


class SearchReportDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    state: Optional[str] = None


class ReportDto(Object):
    id: str
    verification_id: str
    report_version: int
    state: ReportState
    composite_trust_score: Optional[int] = None
    findings: Optional[Dict[str, Any]] = None
    release_reason: Optional[str] = None
    released_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    date_created: datetime
