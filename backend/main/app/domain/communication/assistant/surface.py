"""What the assistant needs from the surface a turn arrived on (PRD §26.6, §16.7, D93).

The engine decides *what to say*; a surface decides *who is asking*, *where a link points*,
*how the reply is delivered* and *which channel facts are recorded*. That split is what lets
one engine answer on WhatsApp and in the web portal without either leaking into the other:

* **WhatsApp** (`channel/whatsapp/bot/surface.py`) — a phone number resolved to an account,
  then to a §26.4.5 delegate, then a stranger; `/wa/*` single-use links; delivery over Meta
  plus a console mirror; STOP/START; non-text media; §26.10 analytics.
* **Web** (`communication/assistant/web.py`) — the signed-in customer who owns the thread;
  direct portal links behind their own login; an in-app reply only; none of the rest.

A surface's copy differs only where the channel does ("this number", "a link that works once
for 15 minutes"). The welcome, the §26.1.4 disclosure, the §26.1.1 pledge, the FAQ, pricing
and status wording are shared, so the two surfaces never describe the product differently.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

from main.app.domain.communication.assistant.capabilities import ChannelAction
from main.app.domain.communication.assistant.reply import BotReply
from main.app.domain.communication.conversation.models import (
    Conversation,
    ConversationChannel,
    ConversationType,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

if TYPE_CHECKING:
    from main.app.domain.communication.assistant.engine import AssistantEngine
    from main.app.domain.communication.assistant.session.models import AssistantSession
    from main.app.domain.verification.models import Verification


class AssistantSurfaceKind(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    WEB = "WEB"


class AssistantEvent(str, enum.Enum):
    """Moments in a conversation a surface may count. WhatsApp maps each to its §26.10 fact
    (D80); the portal counts none of them, so web turns never inflate channel metrics."""

    ENQUIRY = "ENQUIRY"
    INTAKE_STARTED = "INTAKE_STARTED"
    INTAKE_COMPLETED = "INTAKE_COMPLETED"
    PAY_LINK_ISSUED = "PAY_LINK_ISSUED"
    ESCALATED = "ESCALATED"


# The two web thread types the assistant answers: a customer's general-support thread and a
# case's customer↔admin thread. Never admin↔agent — that thread is staff talking to staff.
_WEB_ASSISTANT_THREADS = frozenset(
    {ConversationType.GENERAL_SUPPORT.value, ConversationType.CUSTOMER_ADMIN.value}
)


def assistant_surface_for(conversation: Conversation) -> Optional[AssistantSurfaceKind]:
    """Which surface's assistant answers this thread, or ``None`` if none does.

    A WhatsApp thread is answered on WhatsApp — a customer's in-portal message on it is read
    by a person, because the assistant's reply would go to the phone they are not holding.
    """
    if conversation.channel == ConversationChannel.WHATSAPP.value:
        return AssistantSurfaceKind.WHATSAPP
    if conversation.type in _WEB_ASSISTANT_THREADS:
        return AssistantSurfaceKind.WEB
    return None


@dataclass(frozen=True)
class AssistantDelegate:
    """A §26.4.5 grant: one named person, one case, status only."""

    name: str
    verification_id: str


@dataclass(frozen=True)
class AssistantParty:
    """Who the assistant is talking to, resolved once per turn by the surface.

    Exactly one of three: a customer (an account), a delegate (a grant on one case), or a
    stranger (neither). ``pinned_verification_id`` is set on a case's own thread, where
    "my status" can only mean that case — so the assistant never asks "which one?".
    """

    customer_id: Optional[str] = None
    delegate: Optional[AssistantDelegate] = None
    pinned_verification_id: Optional[str] = None
    phone_e164: Optional[str] = None

    @property
    def is_customer(self) -> bool:
        return self.customer_id is not None


@dataclass(frozen=True)
class AssistantMessage:
    """One inbound turn in the form the engine reads, whatever surface it came from."""

    text: Optional[str]
    kind: InboundKind = InboundKind.TEXT
    # §26.4.1 widget attribution — only ever set on WhatsApp's first message.
    page_code: Optional[str] = None


@dataclass(frozen=True)
class NeedsModel:
    """The deterministic steps could not answer; the turn needs the intent model (D93)."""

    text: str


class SurfaceCopy(Protocol):
    """The sentences that depend on the surface. Everything else lives in `content`."""

    def identity_required(self) -> str: ...

    def pay_with_link(self, link: str) -> str: ...

    def report_with_link(self, link: str) -> str: ...

    def intake_closing(self, link: str) -> str: ...

    def intake_link_again(self, link: str) -> str: ...

    def status_footer(self) -> str: ...


class AssistantSurface(Protocol):
    kind: AssistantSurfaceKind
    copy: SurfaceCopy
    # STOP/START are Meta's opt-out vocabulary (§26.4.6, D64); they mean nothing in the portal.
    handles_consent_keywords: bool

    async def link_for(
        self, action: ChannelAction, party: AssistantParty, verification: "Verification"
    ) -> str:
        """Where a pay, report or upload request is sent for this one case."""
        ...

    async def complete_intake(
        self, session: "AssistantSession", party: AssistantParty, collected: dict
    ) -> str:
        """Turn the four answers into something the customer can finish, returning its link."""
        ...

    async def intake_link_again(self, session: "AssistantSession", party: AssistantParty) -> str:
        """A fresh link for answers already collected (WhatsApp's 15-minute link expires)."""
        ...

    async def deliver(self, conversation: Conversation, reply: BotReply) -> object:
        """Put the reply where the customer reads it. Returns the thread message it became."""
        ...

    async def record(
        self, event: AssistantEvent, session: "AssistantSession", party: AssistantParty, **fields
    ) -> None:
        """A §26.10 channel fact. A no-op off WhatsApp."""
        ...

    async def consent_keyword(
        self, engine: "AssistantEngine", session: "AssistantSession", party: AssistantParty, stop: bool
    ) -> BotReply:
        """Answer STOP or START (only called when `handles_consent_keywords`)."""
        ...

    async def non_text_turn(
        self, engine: "AssistantEngine", session: "AssistantSession", party: AssistantParty, kind: InboundKind
    ) -> BotReply:
        """Answer a photo, document, voice note or pin (§26.6.3)."""
        ...

    async def resume_surface_flow(
        self, engine: "AssistantEngine", session: "AssistantSession", party: AssistantParty, text: str
    ) -> Optional[BotReply]:
        """Let a flow only this surface runs (WhatsApp's `UPLOAD`) read the next message."""
        ...
