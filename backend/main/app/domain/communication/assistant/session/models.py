"""Per-conversation assistant state (PRD §26.3.3, §26.6, §16.7, WA-11).

One row per conversation the assistant answers on — a WhatsApp number's thread, a web support
thread, or a case's customer↔admin thread. It holds only
what a *conversation* needs: where the customer is in a flow, whether a human has taken
over, and how many turns in a row the bot has failed to understand. No case data lives
here; the bot reads that through the same services the dashboard uses (§26.3.1, WA-07), so
there is never a second copy of a verification's state to disagree with the first.

Three fields carry rules rather than data:

* **``mode``** is sticky (D57). Once an agent replies, the bot stops answering until
  someone hands control back from the console — a bot talking over an agent mid-thread is
  the failure customers notice most.
* **``unmatched_count``** is the §26.6.2 escalation trigger: two consecutive unmatched
  intents route to a human. It resets on any turn the bot did understand, so the rule
  means "lost right now", not "lost twice since 2026".
* **``last_inbound_at``** drives the 30-day idle reset (§26.6.1). A customer coming back
  after a month gets the welcome, disclosure and payment pledge again rather than a bot
  resuming a conversation they no longer remember.

On the web a turn that needs the intent model is answered by a second request rather than
inside the customer's send (D93). ``pending_turn_message_id`` marks that turn and
``turn_claimed_at`` is the claim that keeps it single-shot.
"""
from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Index, Integer, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime, jsonb_variant
from sqlalchemy.ext.mutable import MutableDict

# §26.6.1 — "first contact (or after 30 days idle)". Not a setting: it is conversational
# copy policy, and a per-environment value would make the welcome untestable.
WELCOME_IDLE_PERIOD = timedelta(days=30)

# §26.6.2 — "two consecutive unmatched intents" routes to a human.
UNMATCHED_ESCALATION_THRESHOLD = 2


class BotMode(str, enum.Enum):
    """Who is answering this thread (D57).

    ``HUMAN`` is entered when an agent replies from the console and left only by an
    explicit hand-back, so an agent is never interrupted by the bot and the §26.10
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
    # §26.6.3 — the customer sent a document and owns more than one case, so the bot has
    # asked which one it belongs to before it will issue an `upload` link.
    UPLOAD = "UPLOAD"
    # §26.3.4 — the same question for the other two handoffs: which case is being paid for,
    # and which report is being asked for. Separate flows rather than one parameterised
    # `HANDOFF`, because the answer mints a link that authorizes a *different* action, and
    # a session that forgot which one it asked about could hand over the wrong one.
    PAY = "PAY"
    REPORT = "REPORT"


class EscalationReason(str, enum.Enum):
    """Why a conversation went to a human (§26.6.2, §26.10).

    Recorded because §26.10 asks for the escalation rate **and its reasons**: a channel
    escalating on guardrail topics is working as designed, while one escalating on
    unmatched intents is telling us which flow to build next.
    """

    EXPLICIT_REQUEST = "EXPLICIT_REQUEST"            # the customer asked for a person
    GUARDRAIL_TOPIC = "GUARDRAIL_TOPIC"              # §26.6.4 — judgment, legal, assessment
    REFUND_OR_CANCELLATION = "REFUND_OR_CANCELLATION"  # money decisions are never the bot's
    UNMATCHED_INTENTS = "UNMATCHED_INTENTS"          # two consecutive misses
    NON_ENGLISH = "NON_ENGLISH"                      # English only at v1 (Decision L)
    CAPABILITY_NOT_OFFERED = "CAPABILITY_NOT_OFFERED"  # §26.3.4 — not a WhatsApp action
    # §26.6.3 gives voice notes their own row, and §26.10 asks for voice-note volume by
    # name, so they are counted separately from the media the bot merely cannot open.
    VOICE_NOTE = "VOICE_NOTE"                        # §26.6.3 — a person will listen
    UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA"          # §26.6.3 — pins, contacts, stickers, video
    PIPELINE_FAILURE = "PIPELINE_FAILURE"            # §26.6.5 — the bot itself failed


# ─── ORM ──────────────────────────────────────────────────────────

class AssistantSession(BaseEntity):
    __tablename__ = "chat_bot_sessions"

    # The conversation's .hex id. One session per conversation, enforced by the database:
    # two rows would mean two half-remembered conversations with one person.
    conversation_id = Column(String(36), nullable=False)
    # E.164 with the leading '+' for a WhatsApp thread, matching `whatsapp_links.phone_e164`
    # and the conversation's `external_ref`; null on the web. Kept on the row because the
    # intake handoff and erasure both find a WhatsApp conversation's state by its number.
    phone_e164 = Column(String(32), nullable=True)
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
    # A web turn waiting for the intent model (D93): the customer message it answers, when
    # it was left, and when a request claimed it.
    pending_turn_message_id = Column(String(36), nullable=True)
    pending_turn_at = Column(UTCDateTime, nullable=True)
    turn_claimed_at = Column(UTCDateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_chat_bot_sessions_conversation_id"),
        Index("ix_chat_bot_sessions_phone_e164", "phone_e164"),
    )

    @property
    def has_pending_turn(self) -> bool:
        return self.pending_turn_message_id is not None

    def is_welcome_due(self, now: datetime) -> bool:
        """Whether this turn should open with the §26.6.1 welcome.

        True on first contact and after 30 days idle. The disclosure and the payment
        pledge ride on the welcome, so this is also the answer to "has this person been
        told they are talking to a bot, recently enough to remember".
        """
        if self.welcomed_at is None:
            return True
        return (now - self.welcomed_at) >= WELCOME_IDLE_PERIOD


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAssistantSessionDto(Object):
    conversation_id: str
    phone_e164: Optional[str] = None
    mode: BotMode = BotMode.BOT
    current_flow: Optional[BotFlow] = None
    step: int = 0
    context: Optional[dict] = None
    last_inbound_at: Optional[datetime] = None


class UpdateAssistantSessionDto(Object):
    mode: Optional[BotMode] = None
    current_flow: Optional[BotFlow] = None
    step: Optional[int] = None
    last_escalation_reason: Optional[EscalationReason] = None


class QueryAssistantSessionDto(BaseQueryDto):
    conversation_id: Optional[str] = None
    phone_e164: Optional[str] = None
    mode: Optional[str] = None


class SearchAssistantSessionDto(InternalPageRequest, BaseQueryDto):
    mode: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class AssistantSessionDto(Object):
    """What the admin console shows beside a thread the assistant can answer.

    ``enabled`` is false for a thread the assistant never answers (an admin↔agent thread),
    and the console then shows nothing. The mode is the load-bearing part: D57 leaves a
    thread bot-less until someone hands control back, so an agent has to be able to see
    that the assistant is silent and why.

    ``window_open`` is set only on a WhatsApp thread — the second thing an agent needs
    *before* typing (§26.7): outside Meta's 24-hour window their reply is queued behind a
    `window_reopen` nudge rather than delivered as written.
    """

    conversation_id: str
    enabled: bool = True
    phone_e164: Optional[str] = None
    mode: BotMode = BotMode.BOT
    mode_changed_at: Optional[datetime] = None
    current_flow: Optional[BotFlow] = None
    last_inbound_at: Optional[datetime] = None
    window_open: Optional[bool] = None
    last_escalation_reason: Optional[EscalationReason] = None
    last_escalated_at: Optional[datetime] = None


class AssistantReadinessDto(Object):
    """Is the channel wired for live traffic? (§26.11 launch gate.)

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
