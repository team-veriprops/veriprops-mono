"""The assistant in the web portal (PRD §16.7, D93).

The portal half of the surface-neutral assistant. It answers a customer's general-support
thread and a case's customer↔admin thread — never admin↔agent, which is staff talking to
staff, and never a WhatsApp thread, which the WhatsApp surface answers.

What makes this surface different is *who is asking and how they wait*:

* **The party is the signed-in customer who owns the thread**, derived from the thread
  itself, never from the request. On a case's own thread the case is pinned, so "my status"
  or "how do I pay?" never asks "which one?".
* **Links go straight to the portal page** behind the customer's own login — no `/wa/*`
  tokens, which exist only because a WhatsApp number is not a session.
* **The reply is an in-app message** (a `SYSTEM` post into the thread), never a WhatsApp send.
* **No STOP/START, no media, no §26.10 facts** — none of them mean anything here.

**Two requests per model turn (D93).** Every environment runs serverless today, where work
after a response can be frozen and the in-process scheduler cannot be relied on. So phase one
(everything deterministic) answers *inside the customer's send*, and only a turn that needs
the intent model is left pending on the session: the client then calls the turn endpoint,
which claims the turn atomically and answers it in that request. A page that loads with a
turn still pending asks again, and the claim keeps it single-shot. The sweep
(`check_pending_assistant_turns`) is the backstop once long-running hosts exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kink import inject

from main.app.core.links.portal import (
    VerificationPage,
    absolute_url,
    new_verification_path,
    verification_path,
)
from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.assistant import content
from main.app.domain.communication.assistant.capabilities import ChannelAction
from main.app.domain.communication.assistant.engine import AssistantEngine
from main.app.domain.communication.assistant.intake_seeder import IntakeDraftSeeder
from main.app.domain.communication.assistant.reply import BotReply
from main.app.domain.communication.assistant.session.models import AssistantSession
from main.app.domain.communication.assistant.session.service import (
    AssistantSessionService,
    AssistantTurnClaims,
)
from main.app.domain.communication.assistant.surface import (
    AssistantEvent,
    AssistantMessage,
    AssistantParty,
    AssistantSurfaceKind,
    assistant_surface_for,
)
from main.app.domain.communication.chat_message.models import (
    ChatMessage,
    MessageKind,
    MessageSource,
    SenderKind,
)
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import Conversation, ConversationType
from main.app.domain.communication.conversation.repo import ConversationRepo
from main.app.domain.verification.models import Verification
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

# Portal page per handoff. Media never arrives on the web, but an upload request still has
# a page to go to.
_HANDOFF_PAGES: dict[ChannelAction, VerificationPage] = {
    ChannelAction.PAY: VerificationPage.PAY,
    ChannelAction.VIEW_REPORT: VerificationPage.REPORT,
    ChannelAction.UPLOAD_DOCUMENTS: VerificationPage.EVIDENCE,
}


@dataclass(frozen=True)
class AssistantOutcome:
    """What a customer's send (or a turn request) produced from the assistant.

    ``reply`` is the in-app message the assistant posted, when it answered; ``pending`` says a
    turn is still waiting for the intent model, so the client should ask for it.
    """

    reply: Optional[ChatMessage] = None
    pending: bool = False


class WebCopy:
    """The portal's wording where the surface changes the sentence: the reader is signed in,
    and a link is a page, not a token that expires."""

    def identity_required(self) -> str:
        return content.portal_identity_required()

    def pay_with_link(self, link: str) -> str:
        return content.pay_with_portal_link(link)

    def report_with_link(self, link: str) -> str:
        return content.report_with_portal_link(link)

    def intake_closing(self, link: str) -> str:
        return content.intake_portal_closing(link)

    def intake_link_again(self, link: str) -> str:
        return content.intake_portal_link_again(link)

    def status_footer(self) -> str:
        return content.PORTAL_STATUS_FOOTER


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WebAssistantSurface:
    kind = AssistantSurfaceKind.WEB
    copy = WebCopy()
    handles_consent_keywords = False

    def __init__(
        self,
        chat_message_service: ChatMessageService,
        assistant_session_service: AssistantSessionService,
        intake_draft_seeder: IntakeDraftSeeder,
    ):
        self._chat = chat_message_service
        self._sessions = assistant_session_service
        self._intake_draft_seeder = intake_draft_seeder

    async def link_for(
        self, action: ChannelAction, party: AssistantParty, verification: Verification
    ) -> str:
        page = _HANDOFF_PAGES[action]
        return absolute_url(verification_path(Utils.uuid_to_hex(verification.id), page))

    async def complete_intake(
        self, session: AssistantSession, party: AssistantParty, collected: dict
    ) -> str:
        """The customer is already signed in, so the answers become their draft now and the
        wizard resumes it — nothing is kept on the session to redeem later."""
        await self._intake_draft_seeder.seed(party.customer_id, collected)
        await self._sessions.clear_flow(session)
        return absolute_url(new_verification_path())

    async def intake_link_again(self, session: AssistantSession, party: AssistantParty) -> str:
        return absolute_url(new_verification_path())

    async def deliver(self, conversation: Conversation, reply: BotReply) -> ChatMessage:
        # SYSTEM + SYSTEM_AUTO: platform copy, exempt from the fraud scan — it carries
        # veriprops.ng links by design (see `ChatMessageService.send`).
        return await self._chat.send(
            conversation, None, SenderKind.SYSTEM, reply.text,
            kind=MessageKind.SYSTEM_AUTO, source=MessageSource.WEB,
        )

    async def record(
        self, event: AssistantEvent, session: AssistantSession, party: AssistantParty, **fields
    ) -> None:
        """§26.10 counts the WhatsApp channel; a portal turn is counted into nothing."""
        return None

    async def consent_keyword(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, stop: bool
    ) -> BotReply:
        return await engine.unmatched(session)

    async def non_text_turn(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, kind: InboundKind
    ) -> BotReply:
        return await engine.unmatched(session)

    async def resume_surface_flow(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, text: str
    ) -> Optional[BotReply]:
        await self._sessions.clear_flow(session)
        return None


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WebAssistantService:
    def __init__(
        self,
        assistant_engine: AssistantEngine,
        web_assistant_surface: WebAssistantSurface,
        assistant_session_service: AssistantSessionService,
        assistant_turn_claims: AssistantTurnClaims,
        conversation_repo: ConversationRepo,
        chat_message_repo: ChatMessageRepo,
        verification_repo: VerificationRepo,
    ):
        self._engine = assistant_engine
        self._surface = web_assistant_surface
        self._sessions = assistant_session_service
        self._claims = assistant_turn_claims
        self._conversations = conversation_repo
        self._messages = chat_message_repo
        self._verifications = verification_repo

    async def after_customer_message(
        self, conversation: Conversation, message: ChatMessage
    ) -> AssistantOutcome:
        """Phase one for a message the customer just sent (D93).

        Answers inline when no model is needed; otherwise leaves the turn pending for the
        client's second request. A newest message always supersedes an older pending one.
        Nothing happens for a message still held by the fraud scan — the assistant answers
        what reached the thread, not what an admin may yet block.
        """
        party = await self._party_for(conversation)
        if not self._answers(conversation, message, party):
            return AssistantOutcome()
        result = await self._engine.answer_without_model(
            conversation, party, AssistantMessage(text=message.body), self._surface
        )
        session = await self._sessions.get(conversation.id)
        if result.needs_model:
            await self._sessions.mark_pending_turn(session, message.id)
            return AssistantOutcome(pending=True)
        if session is not None:
            await self._sessions.clear_pending_turn(session)
        return AssistantOutcome(reply=result.delivered if isinstance(result.delivered, ChatMessage) else None)

    async def run_pending_turn(self, conversation_id: str) -> AssistantOutcome:
        """Phase two: claim the conversation's pending turn and answer it in this request.

        The claim commits on its own before the model is called, so a second request —
        another tab, a reload, the sweep — finds it taken and returns at once. A request
        that loses the race still reports the turn as pending; the winner's reply reaches
        the thread when it lands.
        """
        message_id = await self._claims.claim(conversation_id)
        if message_id is None:
            session = await self._sessions.get(conversation_id)
            return AssistantOutcome(pending=bool(session and session.has_pending_turn))

        conversation = await self._conversations.get_model(conversation_id)
        message = await self._messages.get_model(message_id)
        session = await self._sessions.get(conversation_id)
        if conversation is None or message is None or session is None:
            if session is not None:
                await self._sessions.release_turn(session, message_id)
            return AssistantOutcome()

        party = await self._party_for(conversation)
        result = await self._engine.answer_with_model(
            conversation, party, AssistantMessage(text=message.body), self._surface
        )
        await self._sessions.release_turn(session, message_id)
        reply = result.delivered if isinstance(result.delivered, ChatMessage) else None
        return AssistantOutcome(reply=reply, pending=session.has_pending_turn)

    async def sweep(self, limit: int = 20, waiting_seconds: Optional[float] = None) -> dict:
        """Answer turns nobody asked for — a tab closed between the send and the turn request.

        Not relied on while environments are serverless (the scheduler cannot be); the page's
        own reload recovery is. Each turn is claimed exactly as a request would claim it, so
        the sweep and a customer's request can never both answer one.
        """
        answered = 0
        for conversation_id in await self._claims.claimable(limit, waiting_seconds):
            outcome = await self.run_pending_turn(conversation_id)
            answered += 1 if outcome.reply is not None else 0
        return {"answered": answered}

    async def pending_conversation_ids(self, conversation_ids: list[str]) -> set[str]:
        return await self._sessions.pending_conversation_ids(conversation_ids)

    async def _party_for(self, conversation: Conversation) -> AssistantParty:
        """The customer who owns the thread — read from the thread, never from the request.

        A case thread's `created_by` is whoever opened it first (often an admin), so the
        owner there is the verification's customer, and the case is pinned.
        """
        if conversation.type == ConversationType.CUSTOMER_ADMIN.value and conversation.verification_id:
            verification = await self._verifications.get_model(conversation.verification_id)
            if verification is None:
                return AssistantParty()
            return AssistantParty(
                customer_id=str(verification.customer_id),
                pinned_verification_id=Utils.uuid_to_hex(verification.id),
            )
        return AssistantParty(customer_id=conversation.created_by)

    @staticmethod
    def _answers(conversation: Conversation, message: ChatMessage, party: AssistantParty) -> bool:
        return (
            assistant_surface_for(conversation) == AssistantSurfaceKind.WEB
            and party.is_customer
            and message.sender_kind == SenderKind.CUSTOMER.value
            and message.state == ChatMessageState.DELIVERED.value
            and str(message.sender_user_id) == str(party.customer_id)
        )
