"""Channel analytics facts (PRD §26.10, WA-43; D80).

§26.10 wants seven numbers instrumented "from day one of launch", and four of them are
**rates over a window** — seam conversion, enquiry→intake, escalation rate, opt-in rate.
None of those could be answered by the tables the channel already had:

* `whatsapp_bot_sessions` holds **one mutated row per phone number**. It keeps
  `last_escalation_reason`, so the channel could tell you the most recent reason a
  particular person was handed to a human, and nothing at all about how often that happens.
  `current_flow` is cleared when a flow ends, so an intake that started and finished leaves
  the row indistinguishable from one that never began.
* `audit_logs` is the legal transition ledger the §19.3 pack exports. Bot telemetry in
  there would put conversation noise inside a legally defensible export and blur what an
  "actor" and a "resource" mean.

So this is an **append-only fact table**: one row per countable occurrence, never updated,
never deleted. That shape is what makes every §26.10 metric the same query — count rows of a
type in a window, optionally grouped by one column — and what lets a rate be recomputed for
any period after the fact rather than only forward from the day someone added a counter.

The rows are deliberately thin. A fact carries when it happened, what kind it was, and the
few keys a §26.10 metric groups by; it is not a second copy of the conversation. Anything
richer belongs in the domain table that already owns it.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime, jsonb_variant


class WhatsAppChannelEventType(str, enum.Enum):
    """The countable occurrences behind §26.10's seven metrics.

    Each member exists because a metric needs it, and the set is closed for the same reason
    `BotIntent` is: an unrecognised fact type would be counted into nothing.
    """

    # A conversation began — a number's first inbound, or its first after the 30-day
    # welcome idle period. Carries the `[ref: …]` page code when the customer arrived
    # through the widget, which is §26.10's attribution metric, and is the **denominator**
    # for both the enquiry→intake and escalation rates.
    ENQUIRY = "ENQUIRY"

    # The four-question chat intake opened (§26.3.4's START_INTAKE).
    INTAKE_STARTED = "INTAKE_STARTED"

    # The intake finished and an `intake` handoff link was minted. This is §26.10's seam
    # conversion **denominator** — the moment the customer has answered everything the
    # chat can ask and must cross to the website to go further.
    INTAKE_COMPLETED = "INTAKE_COMPLETED"

    # The customer signed in and the answers became a real draft. Carries the customer and
    # verification the seam produced, which is what ties a later payment back to the
    # channel without putting an origin column on `verifications`.
    INTAKE_REDEEMED = "INTAKE_REDEEMED"

    # A §26.5 `pay` link was handed over in chat (§26.3.4).
    PAY_LINK_ISSUED = "PAY_LINK_ISSUED"

    # A verification this channel produced was paid for — §26.10's seam conversion
    # **numerator**, and the PRD's "single most important number in this channel".
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"

    # The bot handed the conversation to a person, with the `EscalationReason` that sent it
    # there. §26.10 asks for the rate *and its reasons*: escalating on guardrail topics is
    # the channel working as designed, while escalating on unmatched intents names the
    # flow to build next.
    ESCALATED = "ESCALATED"


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppChannelEvent(BaseEntity):
    """One §26.10 fact. Written once, never updated."""

    __tablename__ = "whatsapp_channel_events"

    # When the thing happened, which is not always when the row was written — a fact
    # recorded from an event subscriber can lag its cause. Every metric windows on this,
    # never on `date_created`.
    occurred_at = Column(UTCDateTime, nullable=False)
    event_type = Column(String(32), nullable=False)

    # E.164, matching `whatsapp_bot_sessions.phone_e164`. Nullable because
    # `PAYMENT_COMPLETED` is recorded from a payment, which knows a customer but not
    # necessarily which handset the conversation happened on.
    phone_e164 = Column(String(32), nullable=True)

    # The widget's `[ref: …]` marker (§26.4.1), set on ENQUIRY only. Free text rather than an
    # enum: the codes describe **frontend routes** the backend does not model, and
    # `lib/whatsapp.ts` derives one for any new page without a table edit — so an unknown
    # code here is a new page, not bad data.
    page_code = Column(String(40), nullable=True)

    # `EscalationReason`, on ESCALATED only.
    reason = Column(String(32), nullable=True)

    verification_id = Column(String(36), nullable=True)
    customer_id = Column(String(36), nullable=True)

    # Anything a future metric wants that does not deserve a column yet. Never read by a
    # §26.10 metric — a number that matters earns a column and an index.
    detail = Column(jsonb_variant(), nullable=True)

    __table_args__ = (
        # Every §26.10 metric is "rows of this type in this window", so the composite index
        # is the access path rather than an optimisation.
        Index("ix_whatsapp_channel_events_type_time", "event_type", "occurred_at"),
        Index("ix_whatsapp_channel_events_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppChannelEventDto(Object):
    occurred_at: datetime
    event_type: str
    phone_e164: Optional[str] = None
    page_code: Optional[str] = None
    reason: Optional[str] = None
    verification_id: Optional[str] = None
    customer_id: Optional[str] = None
    detail: Optional[dict] = None


class UpdateWhatsAppChannelEventDto(Object):
    """Intentionally empty. A fact is append-only: correcting one would rewrite history
    that a rate was already computed from."""


class QueryWhatsAppChannelEventDto(BaseQueryDto):
    event_type: Optional[str] = None
    phone_e164: Optional[str] = None
    verification_id: Optional[str] = None


class SearchWhatsAppChannelEventDto(InternalPageRequest, BaseQueryDto):
    event_type: Optional[str] = None


# ─── Meta number health (§26.10, §26.11; D81) ───────────────────────

class WhatsAppQualityRating(str, enum.Enum):
    """Meta's quality rating for the business number.

    §26.10 counts it as the channel's platform-dependency early warning: property is a
    scam-saturated category under aggressive automated enforcement, and the rating is the
    signal that arrives *before* Meta throttles or bans the number. `UNKNOWN` is ours, not
    Meta's — it is the state before a first successful sync, and it must not read as green.
    """

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class WhatsAppNumberHealth(BaseEntity):
    """Meta's verdict on our number, cached (D81).

    The same posture as the §26.7 template registry (D59a): Meta owns the value, we store
    what it last told us alongside *when* it told us, and nothing in the send path ever
    reads this. A stale or failed sync must never be able to take the channel down — the
    admin surface shows the sync age and lets a person judge.

    One row, keyed by the Meta phone-number id, so a number change is a new row rather than
    a silently overwritten history.
    """

    __tablename__ = "whatsapp_number_health"

    phone_number_id = Column(String(64), nullable=False)
    quality_rating = Column(
        String(16), nullable=False, server_default=WhatsAppQualityRating.UNKNOWN.value
    )
    # Meta's rolling 24-hour send allowance ("TIER_1K", "TIER_UNLIMITED", …). Free text:
    # it is Meta's vocabulary and they extend it without notice, so an enum here would
    # turn a new tier into a sync failure.
    messaging_limit_tier = Column(String(32), nullable=True)
    last_synced_at = Column(UTCDateTime, nullable=True)
    # Why the last sync failed, if it did. Kept rather than raised so the admin surface can
    # say "this number is showing GREEN, but we have not been able to ask since Tuesday".
    sync_error = Column(String(255), nullable=True)


class CreateWhatsAppNumberHealthDto(Object):
    phone_number_id: str


class UpdateWhatsAppNumberHealthDto(Object):
    quality_rating: Optional[str] = None
    messaging_limit_tier: Optional[str] = None
    sync_error: Optional[str] = None


class QueryWhatsAppNumberHealthDto(BaseQueryDto):
    phone_number_id: Optional[str] = None


class SearchWhatsAppNumberHealthDto(InternalPageRequest, BaseQueryDto):
    phone_number_id: Optional[str] = None
