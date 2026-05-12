"""Share link domain — S43."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Boolean, Column, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class ShareMode(str, enum.Enum):
    PRIVATE = "PRIVATE"
    LINK_ONLY = "LINK_ONLY"
    PUBLIC = "PUBLIC"
    NAMED_RECIPIENT = "NAMED_RECIPIENT"


class ShareLink(BaseEntity):
    __tablename__ = "share_links"

    verification_id = Column(String(36), nullable=False, index=True)
    mode = Column(String(20), nullable=False, default=ShareMode.PRIVATE.value)
    token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(UTCDateTime, nullable=True)
    revoked_at = Column(UTCDateTime, nullable=True)
    created_by = Column(String(36), nullable=False)


class ShareRecipient(BaseEntity):
    __tablename__ = "share_recipients"

    share_link_id = Column(String(36), nullable=False, index=True)
    email = Column(String(254), nullable=False)
    acknowledged_at = Column(UTCDateTime, nullable=True)


class ShareLinkDto(Object):
    id: str
    verification_id: str
    mode: ShareMode
    token: str
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    created_by: str
    date_created: str


class CreateShareLinkDto(Object):
    verification_id: str
    mode: ShareMode = ShareMode.LINK_ONLY
    token: str
    expires_at: Optional[str] = None
    created_by: str


class UpdateShareLinkDto(Object):
    revoked_at: Optional[str] = None
    mode: Optional[ShareMode] = None


class QueryShareLinkDto(BaseQueryDto):
    verification_id: Optional[str] = None
    token: Optional[str] = None
    mode: Optional[str] = None


class SearchShareLinkDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None


class CreateShareRecipientDto(Object):
    share_link_id: str
    email: str


class UpdateShareRecipientDto(Object):
    acknowledged_at: Optional[str] = None


class QueryShareRecipientDto(BaseQueryDto):
    share_link_id: Optional[str] = None
    email: Optional[str] = None


class CreateShareDto(Object):
    mode: ShareMode = ShareMode.LINK_ONLY
    recipient_email: Optional[str] = None
    expiry_days: int = 30
