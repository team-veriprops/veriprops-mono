"""The assistant on WhatsApp (PRD §26.3–§26.6, D93).

The WhatsApp half of the surface-neutral assistant (`communication/assistant/`). The engine
decides what to say; this adapter supplies everything that is WhatsApp's alone:

* **Who is asking** — resolved once per turn and in a fixed order (D67): the number's linked
  account through `WhatsAppLinkService.resolve_user_for_phone`, the channel's single identity
  lookup (§26.4.3); otherwise a §26.4.5 delegation; otherwise a stranger.
* **Where links point** — §26.5 single-use `/wa/*` links, minted for the case the assistant
  resolved, never for a reference someone typed.
* **How a reply leaves** — over Meta, mirrored into the console thread (`bot/sender.py`).
* **STOP and START** (§26.4.6, D64), non-text media (§26.6.3) and the `UPLOAD` flow it parks.
* **§26.10's facts** (D80), which only this surface counts.

Both phases of a turn run back to back here, inside the webhook: Meta has already decoupled
the customer from the wait, so there is nothing to gain from a second request.
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.core.links.portal import absolute_url
from main.app.domain.channel.whatsapp.analytics.models import WhatsAppChannelEventType
from main.app.domain.channel.whatsapp.analytics.recorder import ChannelEventRecorder
from main.app.domain.channel.whatsapp.bot.flows import media as media_flow
from main.app.domain.channel.whatsapp.bot.sender import WhatsAppBotSender
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentSource
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.app.domain.communication.assistant import content
from main.app.domain.communication.assistant.capabilities import ChannelAction, require_handoff
from main.app.domain.communication.assistant.engine import AssistantEngine
from main.app.domain.communication.assistant.flows import intake as intake_flow
from main.app.domain.communication.assistant.flows import status as status_flow
from main.app.domain.communication.assistant.reply import BotReply
from main.app.domain.communication.assistant.session.models import AssistantSession, BotFlow
from main.app.domain.communication.assistant.session.service import AssistantSessionService
from main.app.domain.communication.assistant.surface import (
    AssistantDelegate,
    AssistantEvent,
    AssistantMessage,
    AssistantParty,
    AssistantSurfaceKind,
)
from main.app.domain.communication.chat_message.models import ChatMessage
from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.verification.delegate.service import CaseDelegateService
from main.app.domain.verification.models import Verification
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    InboundWhatsAppMessage,
)

# Which §26.5 link a handoff action hands off with. Every `HANDOFF` row of §26.3.4 must
# appear here, or the assistant would announce a handoff it has no way to perform.
_HANDOFF_INTENTS: dict[ChannelAction, HandoffIntent] = {
    ChannelAction.UPLOAD_DOCUMENTS: HandoffIntent.UPLOAD,
    ChannelAction.PAY: HandoffIntent.PAY,
    ChannelAction.VIEW_REPORT: HandoffIntent.REPORT,
}

# The assistant's neutral moments, as the §26.10 facts they are counted under (D80).
_CHANNEL_EVENTS: dict[AssistantEvent, WhatsAppChannelEventType] = {
    AssistantEvent.ENQUIRY: WhatsAppChannelEventType.ENQUIRY,
    AssistantEvent.INTAKE_STARTED: WhatsAppChannelEventType.INTAKE_STARTED,
    AssistantEvent.INTAKE_COMPLETED: WhatsAppChannelEventType.INTAKE_COMPLETED,
    AssistantEvent.PAY_LINK_ISSUED: WhatsAppChannelEventType.PAY_LINK_ISSUED,
    AssistantEvent.ESCALATED: WhatsAppChannelEventType.ESCALATED,
}


def handoff_intent_for(action: ChannelAction) -> HandoffIntent:
    """The §26.5 link a handoff action hands off with. Raises for a non-handoff action."""
    require_handoff(action)
    return _HANDOFF_INTENTS[action]


def wa_link(intent: HandoffIntent, token: str) -> str:
    """A `/wa/<intent>/<token>` landing, absolute — it is read inside WhatsApp."""
    return absolute_url(f"/wa/{intent.value}/{token}")


class WhatsAppCopy:
    """WhatsApp's wording where the channel changes the sentence: an unverified number, and
    links that work once for fifteen minutes."""

    def identity_required(self) -> str:
        return content.unlinked_number()

    def pay_with_link(self, link: str) -> str:
        return content.pay_with_link(link)

    def report_with_link(self, link: str) -> str:
        return content.report_with_link(link)

    def intake_closing(self, link: str) -> str:
        return intake_flow.closing_with_link(link)

    def intake_link_again(self, link: str) -> str:
        return content.fresh_intake_link(link)

    def status_footer(self) -> str:
        return status_flow.SIGN_IN_FOOTER


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppAssistantSurface:
    kind = AssistantSurfaceKind.WHATSAPP
    copy = WhatsAppCopy()
    handles_consent_keywords = True

    def __init__(
        self,
        assistant_engine: AssistantEngine,
        assistant_session_service: AssistantSessionService,
        whatsapp_bot_sender: WhatsAppBotSender,
        whatsapp_link_service: WhatsAppLinkService,
        whatsapp_consent_service: WhatsAppConsentService,
        case_delegate_service: CaseDelegateService,
        handoff_token_service: HandoffTokenService,
        channel_event_recorder: ChannelEventRecorder,
        verification_repo: VerificationRepo,
    ):
        self._engine = assistant_engine
        self._sessions = assistant_session_service
        self._sender = whatsapp_bot_sender
        self._whatsapp_link_service = whatsapp_link_service
        self._whatsapp_consent_service = whatsapp_consent_service
        self._case_delegate_service = case_delegate_service
        self._handoff_token_service = handoff_token_service
        self._channel_events = channel_event_recorder
        self._verification_repo = verification_repo

    async def handle(
        self, message: InboundWhatsAppMessage, conversation: Conversation
    ) -> Optional[BotReply]:
        """Answer one inbound message, or stay silent when a human owns the thread.

        Returns the reply that was sent, which is what the drive-through and the §26.6.4
        suite assert on. `None` means the assistant deliberately said nothing.
        """
        party = await self._resolve_party(message.from_phone)
        return await self._engine.answer(
            conversation,
            party,
            AssistantMessage(text=message.text, kind=message.kind, page_code=message.page_code),
            self,
        )

    async def _resolve_party(self, phone_e164: str) -> AssistantParty:
        """Account first, then delegation — the order *is* the access control (D67). A number
        that is both is the customer, whose grant is strictly wider."""
        customer_id = await self._whatsapp_link_service.resolve_user_for_phone(phone_e164)
        if customer_id:
            return AssistantParty(customer_id=customer_id, phone_e164=phone_e164)
        grant = await self._case_delegate_service.resolve_delegate_for_phone(phone_e164)
        delegate = (
            AssistantDelegate(name=grant.name, verification_id=grant.verification_id)
            if grant is not None else None
        )
        return AssistantParty(delegate=delegate, phone_e164=phone_e164)

    # ─── Links ────────────────────────────────────────────────────

    async def link_for(
        self, action: ChannelAction, party: AssistantParty, verification: Verification
    ) -> str:
        intent = handoff_intent_for(action)
        token = await self._handoff_token_service.issue(
            party.customer_id, Utils.uuid_to_hex(verification.id), intent
        )
        return wa_link(intent, token)

    async def complete_intake(
        self, session: AssistantSession, party: AssistantParty, collected: dict
    ) -> str:
        """Keep the answers on the session and hand over an `intake` link (D69/D71).

        The flow ends here rather than parking at `DONE`: a finished intake left parked would
        read the customer's next message as another answer and send a second link. The
        answers survive for the landing, which seeds the draft once the customer signs in.
        """
        await self._sessions.retain_intake(session, collected)
        return await self.intake_link_again(session, party)

    async def intake_link_again(self, session: AssistantSession, party: AssistantParty) -> str:
        token = await self._handoff_token_service.issue_intake(session.phone_e164 or party.phone_e164)
        return wa_link(HandoffIntent.INTAKE, token)

    # ─── Delivery and facts ───────────────────────────────────────

    async def deliver(self, conversation: Conversation, reply: BotReply) -> ChatMessage:
        return await self._sender.reply(conversation, str(conversation.external_ref), reply.text)

    async def record(
        self, event: AssistantEvent, session: AssistantSession, party: AssistantParty, **fields
    ) -> None:
        await self._channel_events.record(
            _CHANNEL_EVENTS[event], phone_e164=session.phone_e164 or party.phone_e164, **fields
        )

    # ─── Messaging consent (§26.4.6, D64) ──────────────────────────
    #
    # Handled by the assistant, in one turn, always. STOP/START are keyword-only — excluded
    # from `CLASSIFIABLE_INTENTS` — so a model can never revoke someone's consent by
    # inference; the customer's literal word is the only thing that reaches here.

    async def consent_keyword(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, stop: bool
    ) -> BotReply:
        if stop:
            return await self._stop_messages(engine, session, party)
        return await self._start_messages(engine, session, party)

    async def _stop_messages(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty
    ) -> BotReply:
        """STOP and its synonyms end **both** §26.4.6 consents (D64)."""
        if not party.is_customer:
            # D77: a delegate has no consent row, so their opt-out has to end the delegation
            # — the only lever a non-user has. A STOP we acknowledge but do not act on is the
            # kind of thing Meta's quality rating is built to notice.
            if party.delegate is not None:
                await self._case_delegate_service.revoke_by_phone(party.phone_e164)
            return await engine.understood(session, content.messages_stopped_unknown_number())
        await self._whatsapp_consent_service.revoke_all(
            party.customer_id, WhatsAppConsentSource.STOP_KEYWORD
        )
        return await engine.understood(session, content.messages_stopped())

    async def _start_messages(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty
    ) -> BotReply:
        """START restores progress updates only; marketing needs the web (D64)."""
        if not party.is_customer:
            # Nothing to restore, and the linking invitation is the honest next step —
            # updates about a case require an account to have a case on.
            return await engine.understood(session, content.unlinked_number())
        await self._whatsapp_consent_service.grant_utility(
            party.customer_id, WhatsAppConsentSource.START_KEYWORD
        )
        return await engine.understood(session, content.messages_restarted())

    # ─── Non-text inbound (§26.6.3) ────────────────────────────────

    async def non_text_turn(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, kind: InboundKind
    ) -> BotReply:
        """Answer a photo, a document, a voice note or a pin (§26.6.3, WA-06/WA-38).

        Identity first, as everywhere that could touch a case (§26.4.3): an `upload` link
        authorizes writing to one specific verification, so it is only ever issued to a
        number proven to belong to the customer who owns that case.
        """
        cases = await engine.load_cases(party)
        outcome = media_flow.render(kind, is_linked=party.is_customer, cases=cases)

        if outcome.is_escalation:
            await self._sessions.clear_flow(session)
            return await engine.escalate(outcome.escalation_reason)

        if outcome.upload_for_vid:
            await self._sessions.clear_flow(session)
            return await engine.understood(
                session, await self._upload_reply(party, cases, outcome.upload_for_vid)
            )

        if outcome.awaits_choice:
            await self._sessions.enter_flow(
                session, BotFlow.UPLOAD, context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._sessions.clear_flow(session)
        return await engine.understood(session, outcome.text)

    async def resume_surface_flow(
        self, engine: AssistantEngine, session: AssistantSession, party: AssistantParty, text: str
    ) -> Optional[BotReply]:
        """The customer picked which case their document belongs to (§26.6.3)."""
        if session.current_flow != BotFlow.UPLOAD.value or not party.is_customer:
            # An unknown flow, or the link was revoked between the question and the answer
            # — re-run identity rather than issuing a token off a stale offer.
            await self._sessions.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        # Re-filtered, not just re-read: a case that moved out of an uploadable state
        # between the question and the answer must stop being selectable.
        cases = [
            case
            for case in media_flow.uploadable_cases(await engine.load_cases(party))
            if case.vid in offered
        ]
        selected = media_flow.resolve_choice(cases, text)
        await self._sessions.clear_flow(session)
        if selected is None:
            # Not a choice — the customer moved on. Classify fresh.
            return None
        return await engine.understood(session, await self._upload_reply(party, cases, selected.vid))

    async def _upload_reply(
        self, party: AssistantParty, cases: List[status_flow.CaseSummary], vid: str
    ) -> str:
        """The evidence rule plus a link that writes to exactly one case.

        The token is minted from the *case the assistant resolved*, never from anything the
        customer typed: a `vid` is printed on receipts and reports, so accepting one at face
        value would let a forwarded document target someone else's file.
        """
        case = next((c for c in cases if c.vid == vid), None)
        verification = await self._verification_repo.get_by_vid(case.vid) if case else None
        if verification is None:
            # The case list changed under us between render and issue.
            return content.document_received_no_case()
        link = await self.link_for(ChannelAction.UPLOAD_DOCUMENTS, party, verification)
        return content.document_received_with_link(link)
