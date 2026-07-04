"""Admin note domain (PRD §6.1/§6.6).

Internal operational notes attached to a verification: pinned/tagged, searchable,
included in the audit export — and **never** visible to customers or agents. A
separate entity from the verification so notes accrete without touching the
aggregate row.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Index, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class AdminNoteCategory(str, enum.Enum):
    """Tag taxonomy for admin notes (PRD §6.1)."""

    OPERATIONAL = "OPERATIONAL"
    QUALITY = "QUALITY"
    RISK = "RISK"
    HANDOVER = "HANDOVER"


# ─── ORM ──────────────────────────────────────────────────────────

class AdminNote(BaseEntity):
    __tablename__ = "admin_notes"

    verification_id = Column(String(36), nullable=False, index=True)
    author_id = Column(String(36), nullable=False)
    category = Column(String(16), nullable=False, default=AdminNoteCategory.OPERATIONAL.value)
    body = Column(Text, nullable=False)
    pinned = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("ix_admin_notes_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAdminNoteDto(Object):
    verification_id: str
    author_id: str
    category: AdminNoteCategory = AdminNoteCategory.OPERATIONAL
    body: str
    pinned: bool = False


class UpdateAdminNoteDto(Object):
    category: Optional[str] = None
    body: Optional[str] = None
    pinned: Optional[bool] = None


class SearchAdminNoteDto(PageRequest, BaseQueryDto):
    verification_id: Optional[str] = None
    category: Optional[str] = None


class QueryAdminNoteDto(BaseQueryDto):
    verification_id: Optional[str] = None
    author_id: Optional[str] = None
    category: Optional[str] = None


class AddAdminNoteDto(Object):
    category: AdminNoteCategory = AdminNoteCategory.OPERATIONAL
    body: str
    pinned: bool = False


class AdminNoteDto(Object):
    id: str
    verification_id: str
    author_id: str
    category: AdminNoteCategory
    body: str
    pinned: bool
    date_created: datetime
