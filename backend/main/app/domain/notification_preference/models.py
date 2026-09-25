"""Notification preference domain (PRD §12.4).

Per-user, per-event email/SMS opt-out. In-app is never disableable (§12.1). Absence of a
row means the platform defaults apply (email/SMS on) — a row only records an override.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Column, Index, String

from main.appodus_utils.db.models import live_unique_index

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


class NotificationPreference(BaseEntity):
    __tablename__ = "notification_preferences"

    user_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)
    email_enabled = Column(Boolean, nullable=False, server_default="true")
    sms_enabled = Column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        Index("ix_notif_prefs_user", "user_id"),
        # One live preference per user and event, so an opt-out can't be shadowed by a twin.
        live_unique_index("uq_notif_prefs_user_event", "user_id", "event_type"),
    )


class CreateNotificationPreferenceDto(Object):
    user_id: str
    event_type: str
    email_enabled: bool = True
    sms_enabled: bool = True


class UpdateNotificationPreferenceDto(Object):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None


class QueryNotificationPreferenceDto(BaseQueryDto):
    user_id: Optional[str] = None
    event_type: Optional[str] = None


class SearchNotificationPreferenceDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None


class SetPreferenceDto(Object):
    event_type: str
    email_enabled: bool = True
    sms_enabled: bool = True


class PreferenceDto(Object):
    event_type: str
    email_enabled: bool
    sms_enabled: bool
