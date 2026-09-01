"""Meta template approval status (PRD §7.7, WA-15/WA-41).

What this table is **not**: the definition of a template. Names, categories and parameter
order are code-owned (`providers/whatsapp/templates.py`, D59a), because the code is what
fills those parameters — a row here that disagreed with the sender would describe
something the app does not do.

What it **is**: Meta's answer about each declared template, synced from
`GET /{waba_id}/message_templates`. A template can be approved, still under review,
rejected with a reason, or paused for quality — and none of that is knowable from our
side. §7.11 gates launch on "all §7.7 templates approved", so somebody has to be able to
look.

Every row starts `NOT_FOUND`: declared by us, unknown to Meta. That is the honest state
before submission, and the one the launch-gate checklist is really asking about.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


class WhatsAppTemplateStatus(str, enum.Enum):
    """Meta's review states, plus the one state only we can be in.

    The Meta values are theirs verbatim so a synced status needs no translation table to
    go wrong in. `NOT_FOUND` is local: we declare the template, Meta has never seen it.
    """

    # Local — declared here, absent from the business account.
    NOT_FOUND = "NOT_FOUND"
    # Meta's vocabulary.
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    IN_APPEAL = "IN_APPEAL"
    REJECTED = "REJECTED"
    PENDING_DELETION = "PENDING_DELETION"
    DELETED = "DELETED"
    DISABLED = "DISABLED"
    PAUSED = "PAUSED"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def from_meta(cls, value: Optional[str]) -> "WhatsAppTemplateStatus":
        """Meta's status string, or `NOT_FOUND` for anything we do not recognise.

        A status we cannot read must never be optimistically treated as approved: the
        launch gate would then pass on a template that cannot be sent.
        """
        try:
            return cls((value or "").upper())
        except ValueError:
            return cls.NOT_FOUND


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppTemplate(BaseEntity):
    __tablename__ = "whatsapp_templates"

    # The Meta template name — also the `AvailableTemplate` slug, which is what keeps the
    # declaration, the Jinja body, this row, and the wire from drifting apart.
    name = Column(String(120), nullable=False)
    category = Column(String(20), nullable=False)
    language = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False)
    # Meta's own id for the template, when it knows of one.
    remote_id = Column(String(64), nullable=True)
    # Why Meta refused it — the only actionable thing about a REJECTED row.
    rejection_reason = Column(Text, nullable=True)
    last_synced_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("name", name="uq_whatsapp_templates_name"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppTemplateDto(Object):
    name: str
    category: str
    language: str
    status: WhatsAppTemplateStatus = WhatsAppTemplateStatus.NOT_FOUND
    remote_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class UpdateWhatsAppTemplateDto(Object):
    category: Optional[str] = None
    language: Optional[str] = None
    status: Optional[WhatsAppTemplateStatus] = None
    remote_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class QueryWhatsAppTemplateDto(BaseQueryDto):
    name: Optional[str] = None
    status: Optional[str] = None


class SearchWhatsAppTemplateDto(InternalPageRequest, BaseQueryDto):
    status: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class WhatsAppTemplateDto(Object):
    """One row of the admin registry."""

    name: str
    category: str
    language: str
    status: WhatsAppTemplateStatus
    rejection_reason: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    # How the template is used, so the page is readable without the PRD open.
    parameters: List[str] = []


class WhatsAppTemplateSyncResultDto(Object):
    """What a sync changed — enough for the admin to see it did something."""

    synced: int
    approved: int
    missing: int
