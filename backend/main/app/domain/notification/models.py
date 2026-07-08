"""Notification domain (PRD §12, §N.4).

An in-app system notification for one user. In-app is always on (§12.1) and cannot be
disabled; email/SMS fan-out is decided by the §4.8 rule table + the user's preferences.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Index, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


class Notification(BaseEntity):
    __tablename__ = "notifications"

    user_id = Column(String(36), nullable=False, index=True)
    type = Column(String(40), nullable=False)   # the EventType value that produced it
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(300), nullable=True)    # in-app deep link (frontend route)
    read = Column(Boolean, nullable=False, server_default="false")
    event_ref = Column(String(36), nullable=True)  # e.g. the verification id

    __table_args__ = (
        Index("ix_notifications_user", "user_id"),
    )


class CreateNotificationDto(Object):
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    event_ref: Optional[str] = None


class UpdateNotificationDto(Object):
    read: Optional[bool] = None


class QueryNotificationDto(BaseQueryDto):
    user_id: Optional[str] = None
    read: Optional[bool] = None


class SearchNotificationDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    read: Optional[bool] = None


class NotificationDto(Object):
    id: str
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    read: bool
    event_ref: Optional[str] = None
    date_created: datetime
