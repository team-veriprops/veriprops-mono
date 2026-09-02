"""Per-conversation bot state (PRD §7.3.3, §7.6, WA-11).

One row per WhatsApp number — the "state-per-conversation" §7.3.3 asks for. It holds only
what a *conversation* needs: where the customer is in a flow, whether a human has taken
over, and how many turns in a row the bot has failed to understand. No case data lives
here; the bot reads that through the same services the dashboard uses (§7.3.1, WA-07), so
there is never a second copy of a verification's state to disagree with the first.

Three fields carry rules rather than data:

* **``mode``** is sticky (D57). Once an agent replies, the bot stops answering until
  someone hands control back from the console — a bot talking over an agent mid-thread is
  the failure customers notice most.
* **``unmatched_count``** is the §7.6.2 escalation trigger: two consecutive unmatched
  intents route to a human. It resets on any turn the bot did understand, so the rule
  means "lost right now", not "lost twice since 2026".
* **``last_inbound_at``** drives the 30-day idle reset (§7.6.1). A customer coming back
  after a month gets the welcome, disclosure and payment pledge again rather than a bot
  resuming a conversation they no longer remember.
"""
from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Integer, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime, jsonb_variant
from sqlalchemy.ext.mutable import MutableDict

# §7.6.1 — "first contact (or after 30 days idle)". Not a setting: it is conversational
# copy policy, and a per-environment value would make the welcome untestable.
WELCOME_IDLE_PERIOD = timedelta(days=30)

# §7.6.2 — "two consecutive unmatched intents" routes to a human.
UNMATCHED_ESCALATION_THRESHOLD = 2


class BotMode(str, enum.Enum):
    """Who is answering this thread (D57).

    ``HUMAN`` is entered when an agent replies from the console and left only by an
    explicit hand-back, so an agent is never interrupted by the bot and the §7.10
    escalation rate is countable rather than inferred.
    """

    BOT = "BOT"
    HUMAN = "HUMAN"


class BotFlow(str, enum.Enum):
    """A multi-step conversation the session is part-way through.

    Null means the bot is between flows and the next message is classified fresh. Only
    flows that genuinely span turns appear here — a one-shot answer (pricing, an FAQ)
    leaves no state behind.
    """

    WELCOME = "WELCOME"
    STATUS = "STATUS"
    INTAKE = "INTAKE"
    # §7.6.3 — the customer sent a document and owns more than one case, so the bot has
    # asked which one it belongs to before it will issue an `upload` link.
    UPLOAD = "UPLOAD"


class EscalationReason(str, enum.Enum):
    """Why a conversation went to a human (§7.6.2, §7.10).

    Recorded because §7.10 asks for the escalation rate **and its reasons**: a channel
    escalating on guardrail topics is working as designed, while one escalating on
    unmatched intents is telling us which flow to build next.
    """

    EXPLICIT_REQUEST = "EXPLICIT_REQUEST"            # the customer asked for a person
    GUARDRAIL_TOPIC = "GUARDRAIL_TOPIC"              # §7.6.4 — judgment, legal, assessment
    REFUND_OR_CANCELLATION = "REFUND_OR_CANCELLATION"  # money decisions are never the bot's
    UNMATCHED_INTENTS = "UNMATCHED_INTENTS"          # two consecutive misses
    NON_ENGLISH = "NON_ENGLISH"                      # English only at v1 (Decision L)
    CAPABILITY_NOT_OFFERED = "CAPABILITY_NOT_OFFERED"  # §7.3.4 — not a WhatsApp action
    # §7.6.3 gives voice notes their own row, and §7.10 asks for voice-note volume by
    # name, so they are counted separately from the media the bot merely cannot open.
    VOICE_NOTE = "VOICE_NOTE"                        # §7.6.3 — a person will listen
    UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA"          # §7.6.3 — pins, contacts, stickers, video
    PIPELINE_FAILURE = "PIPELINE_FAILURE"            # §7.6.5 — the bot itself failed


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppBotSession(BaseEntity):
    __tablename__ = "whatsapp_bot_sessions"

    # E.164 with the leading '+', matching `whatsapp_links.phone_e164` and the
    # conversation's `external_ref`. One session per number, enforced by the database:
    # two rows would mean two half-remembered conversations with one person.
    phone_e164 = Column(String(32), nullable=False)
    mode = Column(String(10), nullable=False, server_default=BotMode.BOT.value)
    mode_changed_at = Column(UTCDateTime, nullable=True)
    current_flow = Column(String(24), nullable=True)
    step = Column(Integer, nullable=False, server_default="0")
    # Flow working state — the fields collected so far, the cases offered for
    # disambiguation. Mutable, so a nested edit is tracked without reassigning the column
    # (fresh `jsonb_variant()` per column, never the shared singleton).
    context = Column(MutableDict.as_mutable(jsonb_variant()), nullable=True)
    last_inbound_at = Column(UTCDateTime, nullable=True)
    welcomed_at = Column(UTCDateTime, nullable=True)
    unmatched_count = Column(Integer, nullable=False, server_default="0")
    last_escalation_reason = Column(String(32), nullable=True)
    last_escalated_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("phone_e164", name="uq_whatsapp_bot_sessions_phone_e164"),
    )

    def is_welcome_due(self, now: datetime) -> bool:
        """Whether this turn should open with the §7.6.1 welcome.

        True on first contact and after 30 days idle. The disclosure and the payment
        pledge ride on the welcome, so this is also the answer to "has this person been
        told they are talking to a bot, recently enough to remember".
        """
        if self.welcomed_at is None:
            return True
        return (now - self.welcomed_at) >= WELCOME_IDLE_PERIOD


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppBotSessionDto(Object):
    phone_e164: str
    mode: BotMode = BotMode.BOT
    current_flow: Optional[BotFlow] = None
    step: int = 0
    context: Optional[dict] = None
    last_inbound_at: Optional[datetime] = None


class UpdateWhatsAppBotSessionDto(Object):
    mode: Optional[BotMode] = None
    current_flow: Optional[BotFlow] = None
    step: Optional[int] = None
    last_escalation_reason: Optional[EscalationReason] = None


class QueryWhatsAppBotSessionDto(BaseQueryDto):
    phone_e164: Optional[str] = None
    mode: Optional[str] = None


class SearchWhatsAppBotSessionDto(InternalPageRequest, BaseQueryDto):
    mode: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class BotSessionDto(Object):
    """What the admin console shows beside a WhatsApp thread.

    The mode is the load-bearing part: D57 leaves a thread bot-less until someone hands
    control back, so an agent has to be able to see that the bot is silent and why.

    ``window_open`` is the second thing an agent needs *before* typing (§7.7): outside
    Meta's 24-hour window their reply will not be delivered as written, it will be queued
    behind a `window_reopen` nudge. Knowing that in advance is the difference between
    writing a short "still here?" and writing a long answer nobody reads for two days.
    """

    phone_e164: str
    mode: BotMode
    mode_changed_at: Optional[datetime] = None
    current_flow: Optional[BotFlow] = None
    last_inbound_at: Optional[datetime] = None
    window_open: bool = False
    last_escalation_reason: Optional[EscalationReason] = None
    last_escalated_at: Optional[datetime] = None


class BotChannelReadinessDto(Object):
    """Is the channel wired for live traffic? (§7.11 launch gate.)

    Configuration only — never a credential. `intent_configured` says a key is present,
    which is the operational fact an operator needs; the key itself is not something an
    endpoint should be able to say.
    """

    whatsapp_provider: str
    intent_provider: str
    intent_model: str
    intent_configured: bool
    # How many threads the bot is currently silent on (D57). A number that only grows is
    # the signal that agents are taking threads over and never handing them back.
    human_mode_sessions: int
