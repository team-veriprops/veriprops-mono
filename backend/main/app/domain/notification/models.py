"""Notification domain models — S39."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Boolean, Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class NotificationEvent(str, enum.Enum):
    # Verification lifecycle
    STATUS_CHANGE = "STATUS_CHANGE"
    # Payment
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    # Tasks / agents
    AGENTS_ASSIGNED = "AGENTS_ASSIGNED"
    JOB_ALERT = "JOB_ALERT"
    # Reports
    REPORT_READY = "REPORT_READY"
    # Messaging
    NEW_MESSAGE = "NEW_MESSAGE"
    # Fraud (admin)
    FRAUD_FLAGGED_MESSAGE = "FRAUD_FLAGGED_MESSAGE"
    # Task review
    REVISION_REQUEST = "REVISION_REQUEST"
    # SLA
    SLA_BREACH = "SLA_BREACH"
    # Post-report
    RECHECK_DECISION = "RECHECK_DECISION"
    DISPUTE_FILED = "DISPUTE_FILED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
    # Payout
    PAYOUT_APPROVED = "PAYOUT_APPROVED"
    PAYOUT_HELD = "PAYOUT_HELD"


# ── ORM ───────────────────────────────────────────────────────────────────────


class Notification(BaseEntity):
    __tablename__ = "notifications"

    recipient_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    entity_type = Column(String(40), nullable=True)
    entity_id = Column(String(36), nullable=True)
    read = Column(Boolean, nullable=False, default=False)


class NotificationDispatch(BaseEntity):
    __tablename__ = "notification_dispatches"

    notification_id = Column(String(36), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    provider_ref = Column(String(200), nullable=True)
    error = Column(Text, nullable=True)


class NotificationPreference(BaseEntity):
    __tablename__ = "notification_preferences"

    user_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)
    email_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    push_enabled = Column(Boolean, nullable=False, default=False)


# ── DTOs ──────────────────────────────────────────────────────────────────────


class NotificationDto(Object):
    id: str
    recipient_id: str
    event_type: str
    title: str
    body: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    read: bool
    date_created: str


class CreateNotificationDto(Object):
    recipient_id: str
    event_type: str
    title: str
    body: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None


class UpdateNotificationDto(Object):
    read: Optional[bool] = None


class SearchNotificationDto(PageRequest, BaseQueryDto):
    recipient_id: Optional[str] = None
    read: Optional[bool] = None


class QueryNotificationDto(BaseQueryDto):
    recipient_id: Optional[str] = None
    read: Optional[bool] = None
    event_type: Optional[str] = None


class NotificationPreferenceDto(Object):
    user_id: str
    event_type: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool


class UpsertNotificationPreferenceDto(Object):
    event_type: str
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False


class CreateNotificationDispatchDto(Object):
    notification_id: str
    channel: str
    status: str = "PENDING"
    provider_ref: Optional[str] = None
    error: Optional[str] = None


class UpdateNotificationDispatchDto(Object):
    status: Optional[str] = None
    provider_ref: Optional[str] = None
    error: Optional[str] = None


class QueryNotificationDispatchDto(BaseQueryDto):
    notification_id: Optional[str] = None
    channel: Optional[str] = None
    status: Optional[str] = None
