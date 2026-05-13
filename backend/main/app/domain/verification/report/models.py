"""Report domain models — S35/S36."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.ext.mutable import MutableDict

from main.appodus_utils import BaseEntity, Object
from main.appodus_utils.db.models import UTCDateTime


# ─── ORM ──────────────────────────────────────────────────────────────────────


class ReportView(BaseEntity):
    """Records the first time a customer acknowledges and reads their report (S35)."""

    __tablename__ = "report_views"

    vid = Column(String(24), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    acknowledged_at = Column(UTCDateTime, nullable=False)
    ip_address = Column(String(64), nullable=True)
    report_version = Column(String(16), nullable=True)


class ReportVersion(BaseEntity):
    """Tracks PDF versions per verification (S36)."""

    __tablename__ = "report_versions"

    vid = Column(String(24), nullable=False, index=True)
    version_string = Column(String(16), nullable=False)  # e.g. "v1.0", "v2.0"
    pdf_s3_key = Column(String(512), nullable=True)
    is_superseded = Column(Boolean, nullable=False, default=False)


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class CreateReportViewDto(Object):
    vid: str
    customer_id: str
    acknowledged_at: datetime
    ip_address: Optional[str] = None
    report_version: Optional[str] = None


class ReportSectionDto(Object):
    title: str
    content: Dict[str, Any]
    tier_required: Optional[str] = None


class ReportDto(Object):
    vid: str
    version: str
    tier: str
    completed_at: Optional[datetime] = None
    property_address: Optional[str] = None
    trust_score: Optional[Decimal] = None
    executive_summary: Optional[str] = None
    registry_findings: Optional[Dict[str, Any]] = None
    physical_findings: Optional[Dict[str, Any]] = None
    boundary_findings: Optional[Dict[str, Any]] = None
    legal_opinion: Optional[Dict[str, Any]] = None
    risk_summary: Optional[str] = None
    has_acknowledged: bool = False


class CreateReportVersionDto(Object):
    vid: str
    version_string: str
    pdf_s3_key: Optional[str] = None
    date_created: datetime
    created_by: Optional[str] = None


class UpdateReportVersionDto(Object):
    pdf_s3_key: Optional[str] = None
    is_superseded: Optional[bool] = None
