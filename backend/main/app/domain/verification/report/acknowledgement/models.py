"""Report acknowledgement domain (PRD §10.1) — the access-gate record.

One row per (customer, report version) the customer has acknowledged before first view.
Recorded against the version so a re-released report re-gates (the customer accepts the
new version). Single-entity child of the report domain.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ReportAcknowledgement(BaseEntity):
    __tablename__ = "report_acknowledgements"

    verification_id = Column(String(36), nullable=False, index=True)
    report_id = Column(String(36), nullable=False)
    report_version = Column(Integer, nullable=False)
    customer_id = Column(String(36), nullable=False, index=True)
    acknowledged_at = Column(UTCDateTime, nullable=False)

    __table_args__ = (
        Index("ix_report_ack_verification", "verification_id"),
        Index("ix_report_ack_customer", "customer_id"),
    )


class CreateReportAcknowledgementDto(Object):
    verification_id: str
    report_id: str
    report_version: int
    customer_id: str
    acknowledged_at: datetime


class UpdateReportAcknowledgementDto(Object):
    acknowledged_at: Optional[datetime] = None


class QueryReportAcknowledgementDto(BaseQueryDto):
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
    report_version: Optional[int] = None


class SearchReportAcknowledgementDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
