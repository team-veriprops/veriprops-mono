"""WhatsApp messaging consent (PRD §7.4.6, Decisions F/P, D63; WA-27).

§7.4.6 asks for two **separate, unticked** opt-ins at payment confirmation — progress
updates (utility) and news/offers (marketing) — revocable from account settings and by
STOP-style keywords in chat. This is where that state lives, and the notification router
is the only thing that reads it (WA-16: enforcement is never left to a send site).

Three properties are deliberate:

* **One row per account.** The two consents are captured together, on one screen, and
  revoked together by STOP (D64), so they share a row rather than each owning one.
* **Granted-ness is derived, never stored.** A row keeps `granted_at` *and* `revoked_at`
  for each consent, and `granted` is computed from the pair. §7.8 wants consent records
  timestamped and exportable, which means the history *is* the record — a boolean beside
  it could only ever drift from the timestamps that justify it (the D73 argument, applied
  to a second place it holds).
* **Provenance is recorded where it is known.** `source` answers "who turned this off —
  the pay screen, the handoff landing, account settings, or a STOP keyword?" at the moment
  it happened, which is the only moment it can be answered honestly.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


class WhatsAppConsentKind(str, enum.Enum):
    """The two §7.4.6 consents. There is no third at v1 — marketing templates are drafted
    only when a consented campaign is planned (P1)."""

    UTILITY = "UTILITY"
    MARKETING = "MARKETING"


class WhatsAppConsentSource(str, enum.Enum):
    """Where a consent decision was made.

    The four capture points §7.4.6 and D64 name, plus the handoff landing D76 added: a
    customer who arrived from chat pays there and would otherwise never be asked.
    """

    PAY_SCREEN = "PAY_SCREEN"                # authenticated web payment step
    WA_PAY_LANDING = "WA_PAY_LANDING"        # /wa/pay/<token>, grant-scoped (D76)
    ACCOUNT_SETTINGS = "ACCOUNT_SETTINGS"    # /account/whatsapp
    STOP_KEYWORD = "STOP_KEYWORD"            # revoked both in chat (D64)
    START_KEYWORD = "START_KEYWORD"          # restored utility in chat (D64)


def consent_granted(granted_at: Optional[datetime], revoked_at: Optional[datetime]) -> bool:
    """Is a consent live, given its two timestamps?

    A later grant beats an earlier revoke, which is what makes re-consenting work without
    clearing the history that records the revocation.
    """
    if granted_at is None:
        return False
    return revoked_at is None or revoked_at < granted_at


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppConsent(BaseEntity):
    __tablename__ = "whatsapp_consents"

    # One row per account (D63). Unique so two concurrent captures cannot create two
    # consent states for the same customer, which the router would then have to choose
    # between.
    user_id = Column(String(36), nullable=False)

    # "Send me progress updates about this verification on WhatsApp" — gates the §7.7
    # milestone templates.
    utility_granted_at = Column(UTCDateTime, nullable=True)
    utility_revoked_at = Column(UTCDateTime, nullable=True)
    utility_source = Column(String(24), nullable=True)

    # "Send me occasional Veriprops news and offers on WhatsApp" — gates all future
    # marketing templates, including the Marketplace launch audience (P1).
    marketing_granted_at = Column(UTCDateTime, nullable=True)
    marketing_revoked_at = Column(UTCDateTime, nullable=True)
    marketing_source = Column(String(24), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_whatsapp_consents_user_id"),
    )

    @property
    def utility(self) -> bool:
        return consent_granted(self.utility_granted_at, self.utility_revoked_at)

    @property
    def marketing(self) -> bool:
        return consent_granted(self.marketing_granted_at, self.marketing_revoked_at)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppConsentDto(Object):
    user_id: str


class UpdateWhatsAppConsentDto(Object):
    """Deliberately narrow: every timestamped field is set on the attached row instead.

    The generic update path runs its DTO through `jsonable_encoder`, which stringifies
    datetimes before binding — asyncpg then rejects a string for a timestamp column. The
    lifecycle transitions therefore mutate the row directly (see the repo).
    """

    utility_source: Optional[str] = None
    marketing_source: Optional[str] = None


class QueryWhatsAppConsentDto(BaseQueryDto):
    user_id: Optional[str] = None


class SearchWhatsAppConsentDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class SetWhatsAppConsentDto(Object):
    """What a consent surface submits.

    Both controls are always sent, because both are always rendered: a partial update
    would make "unticked" and "not shown" indistinguishable on the server.
    """

    utility: bool
    marketing: bool


class WhatsAppConsentDto(Object):
    """What a consent surface renders. Booleans, derived — never the raw timestamps."""

    utility: bool = False
    marketing: bool = False
    utility_updated_at: Optional[datetime] = None
    marketing_updated_at: Optional[datetime] = None
