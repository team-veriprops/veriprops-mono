"""WhatsApp ↔ account link (PRD §7.4.4, WA-23/WA-24/WA-25).

The channel's identity seam. Everything downstream that refuses to read case data to an
unverified number — the status flow, short-code continuation, delegates — asks exactly one
question, and this table is the only thing that answers it: *which account, if any, owns
this WhatsApp number?*

Three properties make that answer trustworthy:

* **One row per account, one number per row.** `user_id` and `phone_e164` are both unique,
  so the §7.4.4 one-to-one rule is enforced by the database rather than by every caller
  remembering to check it.
* **A revoked link releases its number.** `phone_e164` is nullable and cleared on unlink,
  which is what lets a number move to another account later — a unique constraint over a
  retained value would have blocked that forever. The number that was released is not
  forgotten: the audit log records it.
* **ACTIVE is the only state that means anything.** A `PENDING` row is a linking attempt
  in flight, not a link; the resolution lookup ignores it, so an attacker who can start a
  link but not complete its OTP gains nothing.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


class WhatsAppLinkStatus(str, enum.Enum):
    """Where a link sits in its lifecycle.

    Only ``ACTIVE`` grants anything. ``PENDING`` is an OTP awaiting confirmation, and
    ``REVOKED`` is a link the customer ended or replaced — the state that makes the old
    WhatsApp thread go cold (§7.4.4).
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppLink(BaseEntity):
    __tablename__ = "whatsapp_links"

    # One link per account (§7.4.4). A number change rewrites this row rather than
    # adding another, so there is never a moment with two live numbers on one account.
    user_id = Column(String(36), nullable=False)
    # E.164 with the leading '+', matching `users.phone_e164` and the conversation's
    # `external_ref`. Null once revoked, which frees the number for another account.
    phone_e164 = Column(String(32), nullable=True)
    # Meta's digits-only form of the same number, kept so an inbound `wa_id` can be
    # matched without re-deriving it on every message.
    wa_id = Column(String(32), nullable=True)
    status = Column(String(10), nullable=False)
    linked_at = Column(UTCDateTime, nullable=True)
    revoked_at = Column(UTCDateTime, nullable=True)
    revoked_reason = Column(String(120), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_whatsapp_links_user_id"),
        UniqueConstraint("phone_e164", name="uq_whatsapp_links_phone_e164"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppLinkDto(Object):
    user_id: str
    phone_e164: Optional[str] = None
    wa_id: Optional[str] = None
    status: WhatsAppLinkStatus = WhatsAppLinkStatus.PENDING
    linked_at: Optional[datetime] = None


class UpdateWhatsAppLinkDto(Object):
    phone_e164: Optional[str] = None
    wa_id: Optional[str] = None
    status: Optional[WhatsAppLinkStatus] = None
    revoked_reason: Optional[str] = None


class QueryWhatsAppLinkDto(BaseQueryDto):
    user_id: Optional[str] = None
    phone_e164: Optional[str] = None
    status: Optional[str] = None


class SearchWhatsAppLinkDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    status: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class StartWhatsAppLinkDto(Object):
    """Begin (or restart) linking, sending an OTP to the number over WhatsApp."""

    phone_e164: str


class ConfirmWhatsAppLinkDto(Object):
    phone_e164: str
    code: str


class StartWhatsAppLinkFromTokenDto(Object):
    """The §7.4.4 WhatsApp→web direction: the number comes from the signed link, never
    from the request, so the browser cannot nominate a number the bot never messaged."""

    token: str


class ConfirmWhatsAppLinkFromTokenDto(Object):
    token: str
    code: str


class WhatsAppLinkDto(Object):
    """What the account settings page renders.

    Carries no `wa_id` and no ids beyond the link's own — the page needs to show the
    number and its state, nothing more.
    """

    phone_e164: Optional[str] = None
    status: WhatsAppLinkStatus
    linked_at: Optional[datetime] = None


class WhatsAppLinkChallengeDto(Object):
    """The result of starting a link: how long the code lasts, and where it went."""

    phone_e164: str
    resend_after_seconds: int
