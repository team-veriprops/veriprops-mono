"""The assistant engine — one inbound message in, one reply out (PRD §26.6, §16.7, WA-11/WA-14/WA-39).

This is the dispatcher, and dispatch order *is* the safety model. Every turn runs the same
gauntlet, and each gate exists because skipping it produces a specific failure:

1. **Is a human already on this thread?** (D57) The assistant stays silent. Talking over an
   agent is the failure customers notice most.
2. **Does this turn owe a welcome?** (§26.6.1) First contact, or 30 days idle — the
   assistant discloses what it is and repeats the payment pledge before anything else.
3. **Do the customer's own words hit a guardrail?** (§26.6.4) Checked *before* any
   classification, deterministically, so no model — wrong, slow, or jailbroken — can talk
   the assistant into rendering a verdict.
4. **What did they mean?** Menu numbers, keywords and quoted case references first; only
   then the intent model, and only to pick a flow.
5. **Does the intent itself escalate?** (§26.6.2) Judgments, refunds, and asking for a
   person are recognisable but never answerable.
6. **Is this something the assistant does at all?** (§26.3.4) Otherwise: handoff, or a redirect.
7. **Did we understand?** Two consecutive misses route to a human rather than guess again.

And wrapping all of it: **anything that raises becomes a warm handover** (§26.6.5). An
assistant that goes quiet is indistinguishable from a scam that stopped replying, so an
outage answers with an apology and a person — never with silence.

**Two phases, split exactly at the model call (D93).** Steps 1–4 up to the intent model are
deterministic and fast; the model call is the only slow step. `answer_without_model` runs
everything before it and either answers or reports `NeedsModel`; `answer_with_model` runs the
model and the rest. WhatsApp runs both back to back inside the webhook; the portal answers
phase one inside the customer's send and phase two from a second request. The order of the
gates is identical either way, which is what keeps the §26.6.4 guarantees intact.

The engine is surface-neutral: who is asking, where links point, how a reply is delivered
and what the channel counts all come from the `AssistantSurface` the turn arrived on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from logging import Logger
from typing import List, Optional, Union

from kink import di, inject

from main.app.core import fault_injection
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.fault_injection import FaultPoint, InjectedFault
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus
from main.app.domain.communication.assistant import content, guardrails
from main.app.domain.communication.assistant.capabilities import (
    ChannelAction,
    ChannelCapability,
    capability_for,
)
from main.app.domain.communication.assistant.flows import handoff as handoff_flow
from main.app.domain.communication.assistant.flows import intake as intake_flow
from main.app.domain.communication.assistant.flows import status as status_flow
from main.app.domain.communication.assistant.projection import channel_state
from main.app.domain.communication.assistant.reply import BotReply
from main.app.domain.communication.assistant.session.models import (
    AssistantSession,
    BotFlow,
    BotMode,
    EscalationReason,
)
from main.app.domain.communication.assistant.session.service import AssistantSessionService
from main.app.domain.communication.assistant.support_hours import Coverage, SupportHoursService
from main.app.domain.communication.assistant.surface import (
    AssistantEvent,
    AssistantMessage,
    AssistantParty,
    AssistantSurface,
    NeedsModel,
)
from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.property.service import PropertyService
from main.app.domain.user.repo import UserRepo
from main.app.domain.verification.pricing_config.service import PricingConfigService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.app.domain.verification.tracking.labels import customer_status_label
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.intent.models import BotIntent
from main.appodus_utils.integrations.intent.service import IntentService
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

logger: Logger = di["logger"]

# How many of a customer's cases a status disambiguation will offer. A chat message listing
# fifteen properties is unreadable; someone with more than this has a dashboard.
_MAX_CASES_OFFERED = 5

# The kinds that carry words to classify. A menu tap is a button the assistant offered, not
# media; everything else belongs to §26.6.3 on the surface that can receive it.
_TEXT_KINDS = frozenset({InboundKind.TEXT, InboundKind.INTERACTIVE})

# Menu positions (§26.6.1). The welcome offers numbers, so the numbers have to mean
# something on the next turn — a customer replying "3" to a numbered menu and being told
# the assistant did not understand is the most avoidable miss in the whole product.
_MENU_CHOICES = {
    "1": BotIntent.LEARN,
    "2": BotIntent.START_VERIFICATION,
    "3": BotIntent.CHECK_STATUS,
    "4": BotIntent.TALK_TO_HUMAN,
    "5": BotIntent.PRICING,
}

# The keyword-only intents (D64, §26.4.3), matched on the customer's literal words before
# the classifier runs, on a surface that has an opt-out to honour. They are deliberately
# outside the classifier's vocabulary: a model must not revoke someone's consent by inference.
#
# Meta and the customer both treat STOP as binding, so it must never be answered with
# "I didn't understand" — and never with "a person will get back to you" either, because
# an opt-out that waits for the next working day is not an opt-out. D64 fixes the two
# vocabularies: the STOP set revokes **both** §26.4.6 consents, the START set restores
# progress updates **only**.
_KEYWORD_INTENTS = {
    "stop": BotIntent.STOP_MESSAGES,
    "unsubscribe": BotIntent.STOP_MESSAGES,
    "cancel": BotIntent.STOP_MESSAGES,
    "end": BotIntent.STOP_MESSAGES,
    "quit": BotIntent.STOP_MESSAGES,
    "start": BotIntent.START_MESSAGES,
    "unstop": BotIntent.START_MESSAGES,
    "subscribe": BotIntent.START_MESSAGES,
}

# What the closing message invites the customer to say when their intake link has expired.
# Literal phrases, not a classified intent: this is the payment path, and it must answer
# identically every time.
_RESEND_LINK_PHRASES = {
    "pay", "link", "new link", "fresh link", "send the link", "send link",
    "resend", "resend link", "another link", "expired",
}

# `VP-2026-0001` — the case reference a customer is handed on every receipt and report.
_CASE_REFERENCE = re.compile(r"\bVP-\d{4}-\d{3,}\b", re.IGNORECASE)

# Which action each intent is asking for, so §26.3.4 is consulted once per turn rather
# than remembered per flow.
_INTENT_ACTIONS = {
    BotIntent.LEARN: ChannelAction.LEARN,
    BotIntent.PRICING: ChannelAction.LEARN,
    BotIntent.START_VERIFICATION: ChannelAction.START_INTAKE,
    BotIntent.CHECK_STATUS: ChannelAction.CHECK_STATUS,
    BotIntent.TALK_TO_HUMAN: ChannelAction.TALK_TO_HUMAN,
    BotIntent.LINK_ACCOUNT: ChannelAction.CHECK_STATUS,
    BotIntent.PAY: ChannelAction.PAY,
    BotIntent.VIEW_REPORT: ChannelAction.VIEW_REPORT,
}

# The §26.3.4 handoff a parked "which case?" question is waiting on. Both directions are
# needed: the action picks the flow when the question is asked, and the flow picks the
# action back up when the customer answers a turn later.
_HANDOFF_FLOWS: dict[ChannelAction, BotFlow] = {
    ChannelAction.PAY: BotFlow.PAY,
    ChannelAction.VIEW_REPORT: BotFlow.REPORT,
}
_HANDOFF_ACTIONS: dict[BotFlow, ChannelAction] = {
    flow: action for action, flow in _HANDOFF_FLOWS.items()
}


@dataclass(frozen=True)
class TurnResult:
    """What one phase of a turn produced.

    ``silent`` — a human owns the thread (D57). ``needs_model`` — phase one could not answer
    and phase two must run. Otherwise ``reply`` was sent and ``delivered`` is the thread
    message it became (the surface's return value).
    """

    reply: Optional[BotReply] = None
    delivered: object = None
    needs_model: bool = False
    silent: bool = False


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AssistantEngine:
    def __init__(
        self,
        assistant_session_service: AssistantSessionService,
        intent_service: IntentService,
        support_hours_service: SupportHoursService,
        pricing_config_service: PricingConfigService,
        verification_repo: VerificationRepo,
        verification_task_repo: VerificationTaskRepo,
        property_service: PropertyService,
        user_repo: UserRepo,
    ):
        self._sessions = assistant_session_service
        self._intent_service = intent_service
        self._support_hours_service = support_hours_service
        self._pricing_config_service = pricing_config_service
        self._verification_repo = verification_repo
        self._verification_task_repo = verification_task_repo
        self._property_service = property_service
        self._user_repo = user_repo

    # ─── Turns ────────────────────────────────────────────────────

    async def answer(
        self,
        conversation: Conversation,
        party: AssistantParty,
        message: AssistantMessage,
        surface: AssistantSurface,
    ) -> Optional[BotReply]:
        """Both phases back to back — the WhatsApp webhook path. `None` means the assistant
        deliberately said nothing."""
        first = await self.answer_without_model(conversation, party, message, surface)
        if not first.needs_model:
            return first.reply
        second = await self.answer_with_model(conversation, party, message, surface)
        return second.reply

    async def answer_without_model(
        self,
        conversation: Conversation,
        party: AssistantParty,
        message: AssistantMessage,
        surface: AssistantSurface,
    ) -> TurnResult:
        """Phase one: everything up to the intent model, which is fast and deterministic."""
        session = await self._sessions.get_or_open(conversation, phone_e164=party.phone_e164)
        if session.mode == BotMode.HUMAN.value:
            # D57: sticky until someone hands back from the console.
            return TurnResult(silent=True)
        try:
            # §26.11's failure drill, armed only from a non-production dev endpoint and
            # consumed by the first turn that reaches it. Inside the try on purpose: the
            # drill is worthless unless it exercises the same path a real outage takes.
            if fault_injection.consume(FaultPoint.WHATSAPP_BOT_TURN):
                raise InjectedFault("§26.6.5 failure drill")
            decision = await self._decide_without_model(session, party, message, surface)
        except Exception as exc:  # noqa: BLE001 — §26.6.5: never go quiet
            decision = await self._failure(conversation, session, exc)
        if isinstance(decision, NeedsModel):
            return TurnResult(needs_model=True)
        return await self._finish(conversation, session, party, decision, surface)

    async def answer_with_model(
        self,
        conversation: Conversation,
        party: AssistantParty,
        message: AssistantMessage,
        surface: AssistantSurface,
    ) -> TurnResult:
        """Phase two: the intent model, then the intent guardrail and routing."""
        session = await self._sessions.get_or_open(conversation, phone_e164=party.phone_e164)
        if session.mode == BotMode.HUMAN.value:
            # An agent replied while the model was thinking; the agent's answer stands.
            return TurnResult(silent=True)
        try:
            text = (message.text or "").strip()
            result = await self._intent_service.classify(text)
            reply = await self._route_intent(session, party, result.intent, text, surface)
        except Exception as exc:  # noqa: BLE001 — §26.6.5: never go quiet
            reply = await self._failure(conversation, session, exc)
        return await self._finish(conversation, session, party, reply, surface)

    async def _finish(
        self,
        conversation: Conversation,
        session: AssistantSession,
        party: AssistantParty,
        reply: BotReply,
        surface: AssistantSurface,
    ) -> TurnResult:
        if reply.is_escalation:
            await self._sessions.note_escalation(session, reply.escalation_reason)
            # §26.10 wants the escalation *rate and its reasons*. Every reason funnels
            # through here, so one fact covers all of them — and a new reason is counted
            # the day it is added.
            await surface.record(
                AssistantEvent.ESCALATED, session, party, reason=reply.escalation_reason
            )
        delivered = await surface.deliver(conversation, reply)
        return TurnResult(reply=reply, delivered=delivered)

    async def _failure(
        self, conversation: Conversation, session: AssistantSession, exc: Exception
    ) -> BotReply:
        logger.exception(f"Assistant turn failed on conversation {conversation.id}: {exc}")
        await self._alert_admins(conversation, session)
        return BotReply(
            content.failure_fallback(await self._coverage()), EscalationReason.PIPELINE_FAILURE
        )

    # ─── The gauntlet ─────────────────────────────────────────────

    async def _decide_without_model(
        self,
        session: AssistantSession,
        party: AssistantParty,
        message: AssistantMessage,
        surface: AssistantSurface,
    ) -> Union[BotReply, NeedsModel]:
        welcome_due = await self._sessions.record_inbound(session)
        if welcome_due:
            # §26.10's definition of an enquiry: first contact, or the first message after
            # the idle gap. `page_code` is only ever on the message that starts it (D85).
            await surface.record(AssistantEvent.ENQUIRY, session, party, page_code=message.page_code)
            # The welcome answers the turn on its own. A customer's first message is
            # usually "hi", and an assistant that greeted *and* answered would bury the
            # disclosure and the payment pledge under a wall of text.
            return BotReply(content.welcome())

        # §26.6.3 owns any non-text turn, caption or not. It runs before the guardrails
        # because a caption is not what is being answered — the *thing that arrived* is,
        # and the answers §26.6.3 gives are all safe ones.
        if message.kind not in _TEXT_KINDS:
            return await surface.non_text_turn(self, session, party, message.kind)

        text = (message.text or "").strip()
        if not text:
            return await self.unmatched(session)

        verdict = guardrails.check_message(text)
        if verdict:
            return await self.escalate(verdict.reason)

        # A parked flow reads the message in its own context before anything else — the
        # customer is answering the question the assistant just asked.
        parked = await self._resume_flow(session, party, text, surface)
        if parked:
            return parked

        # A finished intake whose link has probably expired. Matched on the customer's
        # literal words rather than by classification: the closing message told them to
        # say this, and a money path should answer the same way every time.
        if self._wants_a_fresh_link(session, text):
            link = await surface.intake_link_again(session, party)
            return await self.understood(session, surface.copy.intake_link_again(link))

        intent = self._deterministic_intent(text, surface)
        if intent is None:
            return NeedsModel(text)
        return await self._route_intent(session, party, intent, text, surface)

    @staticmethod
    def _deterministic_intent(text: str, surface: AssistantSurface) -> Optional[BotIntent]:
        """Menu numbers, opt-out keywords and quoted references — or ``None`` for the model.

        The menu is deterministic and the model is not, so a customer who replies with a
        number gets the same answer every time — and a model outage cannot break the one
        path the welcome explicitly invited them to use.
        """
        message = text.strip()
        choice = _MENU_CHOICES.get(message)
        if choice:
            return choice
        if surface.handles_consent_keywords:
            keyword = _KEYWORD_INTENTS.get(message.lower())
            if keyword:
                return keyword
        if _CASE_REFERENCE.search(message):
            # The customer quoted a case reference. That is a literal fact about the
            # message, not an inference, so it outranks whatever a model makes of the
            # surrounding words.
            return BotIntent.CONTINUE_CASE
        return None

    async def _route_intent(
        self,
        session: AssistantSession,
        party: AssistantParty,
        intent: BotIntent,
        text: str,
        surface: AssistantSurface,
    ) -> BotReply:
        verdict = guardrails.check_intent(intent)
        if verdict:
            return await self.escalate(verdict.reason)
        return await self._route(session, party, intent, text, surface)

    async def _route(
        self,
        session: AssistantSession,
        party: AssistantParty,
        intent: BotIntent,
        text: str,
        surface: AssistantSurface,
    ) -> BotReply:
        action = _INTENT_ACTIONS.get(intent)
        if action and capability_for(action) == ChannelCapability.NOT_OFFERED:
            return BotReply(content.account_management_not_offered())

        if intent == BotIntent.MENU:
            return await self.understood(session, content.menu())
        if intent == BotIntent.LEARN:
            topic = content.faq_topic_for(text)
            answer = content.faq_answer(topic) if topic else content.learn()
            return await self.understood(session, answer)
        if intent == BotIntent.PRICING:
            view = await self._pricing_config_service.view()
            return await self.understood(session, content.pricing(view))
        if intent == BotIntent.CHECK_STATUS:
            return await self._status(session, party, surface)
        if intent == BotIntent.LINK_ACCOUNT:
            # The linking flow itself lives with the surface that has something to link;
            # here the assistant only points at it.
            return await self.understood(session, surface.copy.identity_required())
        if intent in (BotIntent.STOP_MESSAGES, BotIntent.START_MESSAGES):
            if not surface.handles_consent_keywords:
                return await self.unmatched(session)
            return await surface.consent_keyword(
                self, session, party, stop=intent == BotIntent.STOP_MESSAGES
            )
        if intent == BotIntent.CONTINUE_CASE:
            return await self._continue_case(session, party, text, surface)
        if intent == BotIntent.START_VERIFICATION:
            return await self._begin_intake(session, party, surface)
        if action in _HANDOFF_FLOWS:
            return await self._handoff(session, party, action, surface)

        return await self.unmatched(session)

    # ─── Status ───────────────────────────────────────────────────

    async def _status(
        self, session: AssistantSession, party: AssistantParty, surface: AssistantSurface
    ) -> BotReply:
        """§26.4.3 — identity first, then the same data the dashboard reads.

        The surface resolved identity in a fixed order (D67): *whose account is this?*, then
        *does it hold a delegation?*. The order is the access control — a party that is both
        resolves as the customer, because the account grant is strictly wider and reading it
        as a delegate would lose that person their own data.
        """
        if not party.is_customer:
            delegate_reply = await self._delegate_status(session, party)
            if delegate_reply is not None:
                return delegate_reply
            # One message serves the customer on a second handset and the third party
            # asking about someone else's case: the assistant cannot tell them apart, so it
            # names both routes rather than guessing (§26.4.3 + §26.4.5).
            return await self.understood(session, surface.copy.identity_required())

        cases = await self.load_cases(party)
        outcome = status_flow.render(cases, footer=surface.copy.status_footer())
        if outcome.awaits_choice:
            await self._sessions.enter_flow(
                session, BotFlow.STATUS, context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._sessions.clear_flow(session)
        return await self.understood(session, outcome.text)

    async def _delegate_status(
        self, session: AssistantSession, party: AssistantParty
    ) -> Optional[BotReply]:
        """The status reply for an authorized delegate, or ``None`` if this is not one.

        It reads the one case the delegation names — never a customer's list — and the
        reply carries no report link, because `render_for_delegate` has no path to one.
        """
        if party.delegate is None:
            return None
        case = await self._load_case(party.delegate.verification_id)
        if case is None:
            # The delegation outlived its verification. Nothing to report, and inventing
            # a status would be worse than treating them as a new enquiry.
            return None
        await self._sessions.clear_flow(session)
        return await self.understood(
            session, status_flow.render_for_delegate(case, party.delegate.name).text
        )

    # ─── Pay and report handoffs (§26.3.4, §26.4.2) ─────────────────

    async def _handoff(
        self,
        session: AssistantSession,
        party: AssistantParty,
        action: ChannelAction,
        surface: AssistantSurface,
    ) -> BotReply:
        """Answer "how do I pay?" or "send me my report" with a link (WA-17).

        Identity first, as everywhere that could touch a case (§26.4.3): the link names a
        customer *and* a case, so it is only ever issued to a party proven to be the person
        whose money — or whose report — is involved.
        """
        cases = await self.load_cases(party) if party.is_customer else []
        outcome = handoff_flow.render(action, is_linked=party.is_customer, cases=cases)

        if outcome.link_for_vid:
            await self._sessions.clear_flow(session)
            return await self.understood(
                session,
                await self._handoff_reply(session, party, action, cases, outcome.link_for_vid, surface),
            )

        if outcome.awaits_choice:
            await self._sessions.enter_flow(
                session, _HANDOFF_FLOWS[action], context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._sessions.clear_flow(session)
        return await self.understood(session, outcome.text)

    async def _handoff_reply(
        self,
        session: AssistantSession,
        party: AssistantParty,
        action: ChannelAction,
        cases: List[status_flow.CaseSummary],
        vid: str,
        surface: AssistantSurface,
    ) -> str:
        """The link for exactly one case, and the right words around it.

        The link is built from the *case the assistant resolved*, never from a reference the
        customer typed: a pay link accepted at face value would let a forwarded message send
        someone to pay for a stranger's verification.
        """
        case = next((c for c in cases if c.vid == vid), None)
        verification = await self._verification_repo.get_by_vid(case.vid) if case else None
        if verification is None:
            # The case list changed under us between render and issue. Say the honest
            # thing rather than linking a case we can no longer name.
            return handoff_flow.render(action, is_linked=True, cases=[]).text

        link = await surface.link_for(action, party, verification)
        if action == ChannelAction.PAY:
            # §26.10 counts the pay handoff as a channel-produced case: this fact is what
            # later lets `PAYMENT_CONFIRMED` be attributed to the channel.
            await surface.record(
                AssistantEvent.PAY_LINK_ISSUED, session, party,
                verification_id=Utils.uuid_to_hex(verification.id),
                customer_id=party.customer_id,
            )
            return surface.copy.pay_with_link(link)
        return surface.copy.report_with_link(link)

    async def _resume_handoff(
        self,
        session: AssistantSession,
        party: AssistantParty,
        flow: BotFlow,
        text: str,
        surface: AssistantSurface,
    ) -> Optional[BotReply]:
        """The customer picked which case they meant (§26.3.4)."""
        action = _HANDOFF_ACTIONS[flow]
        if not party.is_customer:
            # The link was revoked between the question and the answer — re-run identity
            # rather than issuing a link off a stale offer.
            await self._sessions.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        # Re-filtered, not just re-read: a case that stopped being payable — or whose
        # report was pulled — between the question and the answer must stop being
        # selectable.
        cases = [
            case
            for case in handoff_flow.eligible_cases(action, await self.load_cases(party))
            if case.vid in offered
        ]
        selected = handoff_flow.resolve_choice(cases, text)
        await self._sessions.clear_flow(session)
        if selected is None:
            # Not a choice — the customer moved on. Classify fresh.
            return None
        return await self.understood(
            session,
            await self._handoff_reply(session, party, action, cases, selected.vid, surface),
        )

    async def _resume_flow(
        self,
        session: AssistantSession,
        party: AssistantParty,
        text: str,
        surface: AssistantSurface,
    ) -> Optional[BotReply]:
        """Let a parked flow answer, or hand the turn back to normal classification."""
        if not session.current_flow:
            return None
        if session.current_flow == BotFlow.INTAKE.value:
            return await self._continue_intake(session, party, text, surface)
        if session.current_flow in (BotFlow.PAY.value, BotFlow.REPORT.value):
            return await self._resume_handoff(
                session, party, BotFlow(session.current_flow), text, surface
            )
        if session.current_flow != BotFlow.STATUS.value:
            return await surface.resume_surface_flow(self, session, party, text)
        if not party.is_customer:
            # The link was revoked between the question and the answer. Falling through
            # re-runs the identity check rather than answering from a stale offer.
            await self._sessions.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        cases = [case for case in await self.load_cases(party) if case.vid in offered]
        outcome = status_flow.render_choice(cases, text, footer=surface.copy.status_footer())
        await self._sessions.clear_flow(session)
        if outcome is None:
            # Not a choice — the customer moved on. Classify fresh.
            return None
        return await self.understood(session, outcome.text)

    # ─── Short-code continuation (§26.4.3, D58) ────────────────────

    async def _continue_case(
        self,
        session: AssistantSession,
        party: AssistantParty,
        text: str,
        surface: AssistantSurface,
    ) -> BotReply:
        """Pick a case up from its reference — "continue VP-2026-0001" (D58).

        Identity first, as everywhere else that touches a case (§26.4.3): quoting a
        reference is not proof of owning it, and references appear on receipts and reports
        that get forwarded. A reference that is not the customer's own is answered as *not
        found* rather than "that is not yours" — confirming a case exists would make the
        reference space probeable.
        """
        if not party.is_customer:
            return await self.understood(session, surface.copy.identity_required())

        quoted = _CASE_REFERENCE.search(text or "")
        cases = await self.load_cases(party)
        match = next(
            (case for case in cases if quoted and case.vid.upper() == quoted.group(0).upper()),
            None,
        )
        if match is None:
            return await self.understood(session, content.case_not_found())

        await self._sessions.clear_flow(session)
        return await self.understood(
            session, status_flow.render([match], footer=surface.copy.status_footer()).text
        )

    # ─── Intake (§5.1, D69/D70) ───────────────────────────────────

    async def _begin_intake(
        self, session: AssistantSession, party: AssistantParty, surface: AssistantSurface
    ) -> BotReply:
        """Open the four-question intake (§26.3.4 lists it as a full capability).

        No account is required to start on WhatsApp: the answers live on the session and
        identity is established at the handoff landing (D69), so a stranger's first message
        can begin a verification.
        """
        outcome = intake_flow.begin()
        await self._park_intake(session, outcome)
        await surface.record(AssistantEvent.INTAKE_STARTED, session, party)
        return await self.understood(session, outcome.text)

    async def _continue_intake(
        self,
        session: AssistantSession,
        party: AssistantParty,
        text: str,
        surface: AssistantSurface,
    ) -> Optional[BotReply]:
        """Apply one answer. Returns `None` if the customer has left the flow.

        A guardrail hit or an explicit "talk to a human" is handled before this runs, so
        anything reaching here is a genuine attempt at the current question — except a
        message that reads like a different intent entirely, which the abandon check below
        hands back to normal classification rather than forcing into a form.
        """
        if self._is_abandoning_intake(text):
            await self._sessions.clear_flow(session)
            return None

        collected = (session.context or {}).get("intake") or {}
        step = intake_flow.IntakeStep(session.step or 0)
        outcome = intake_flow.answer(step, text, collected, await self._pricing_config_service.view())

        if not outcome.complete:
            await self._park_intake(session, outcome)
            # A re-ask is not a failure to understand the customer — it is the flow doing
            # its job — so it must not count toward the §26.6.2 two-strikes escalation.
            return await self.understood(session, outcome.text)

        # §26.10's seam-conversion denominator: the customer has answered everything the
        # chat can ask. Recorded here rather than where a link is issued, which a *resend*
        # also does — counting a re-issued link as a second completed intake would deflate
        # the headline rate.
        await surface.record(AssistantEvent.INTAKE_COMPLETED, session, party)
        link = await surface.complete_intake(session, party, outcome.collected)
        return await self.understood(session, surface.copy.intake_closing(link))

    async def _park_intake(
        self, session: AssistantSession, outcome: intake_flow.IntakeOutcome
    ) -> None:
        await self._sessions.enter_flow(
            session, BotFlow.INTAKE, step=int(outcome.step),
            context={"intake": outcome.collected},
        )

    @staticmethod
    def _wants_a_fresh_link(session: AssistantSession, text: str) -> bool:
        """Whether this is a request to re-send an intake link we can still fill.

        Requires retained answers, so "pay" from someone who never ran an intake still
        classifies normally rather than getting a link to nothing.
        """
        if not (session.context or {}).get("intake"):
            return False
        return (text or "").strip().lower() in _RESEND_LINK_PHRASES

    @staticmethod
    def _is_abandoning_intake(text: str) -> bool:
        """Whether a mid-intake message is really about something else.

        Deliberately narrow: almost anything can be a valid answer to "where is it?", so
        only an unmistakable change of subject drops the flow. Getting this wrong in the
        eager direction would throw away a half-finished intake because someone typed an
        address containing the word "price".
        """
        message = (text or "").strip().lower()
        return message in {
            "menu", "cancel", "stop", "start over", "restart", "help", "pricing",
        }

    # ─── Case data ────────────────────────────────────────────────

    async def load_cases(self, party: AssistantParty) -> List[status_flow.CaseSummary]:
        """The customer's cases, read through the same repo the dashboard list uses.

        §26.3.1's "same API endpoints the website dashboard uses" in practice: the status
        strings come from `tracking/labels.py`, so the surfaces cannot describe one case
        differently. On a case's own thread the list is that one case — "my status" there
        can only mean it — and it is still checked to be the customer's.
        """
        if not party.customer_id:
            return []
        if party.pinned_verification_id:
            pinned = await self._load_case(party.pinned_verification_id, owner_id=party.customer_id)
            return [pinned] if pinned else []
        rows, _ = await self._verification_repo.page_for_customer(
            party.customer_id, offset=0, limit=_MAX_CASES_OFFERED
        )
        return [await self._summarise(row) for row in rows]

    async def _load_case(
        self, verification_id: str, owner_id: Optional[str] = None
    ) -> Optional[status_flow.CaseSummary]:
        """One case, summarised exactly as `load_cases` summarises a customer's list.

        Keyed by id rather than by customer, because a delegate is granted *this case* and
        has no list to page. With *owner_id* the case must also be that customer's.
        """
        row = await self._verification_repo.get_model(verification_id)
        if row is None:
            return None
        if owner_id is not None and str(row.customer_id) != str(owner_id):
            return None
        return await self._summarise(row)

    async def _summarise(self, row) -> status_flow.CaseSummary:
        status = VerificationStatus(row.status)
        return status_flow.CaseSummary(
            vid=row.vid,
            property_label=await self._property_label(row.property_id),
            status_label=customer_status_label(status),
            channel_state=channel_state(
                status, await self._field_task_state(Utils.uuid_to_hex(row.id))
            ),
            sla_due_date=row.sla_due_date,
        )

    async def _property_label(self, property_id: Optional[str]) -> str:
        """A one-line address for the property, or a neutral stand-in.

        A draft can exist before its property does, and "your verification" is a better
        answer than an empty line or a raw id.
        """
        if not property_id:
            return "Your property"
        try:
            prop = await self._property_service.get_model(property_id)
        except Exception:  # noqa: BLE001 — a missing property must not fail a status turn
            return "Your property"
        if prop is None:
            return "Your property"
        # `landmark` is the §5.1 escape valve for a plot Google Places could not resolve,
        # so it is the right stand-in when there is no formatted address.
        parts = [part for part in (prop.address or prop.landmark, prop.lga, prop.state) if part]
        return ", ".join(parts) if parts else "Your property"

    async def _field_task_state(self, verification_id: str) -> Optional[TaskState]:
        """The FIELD task's state, which is what separates `verifying` from
        `field_inspection` in the §26.3.2 projection."""
        task = await self._verification_task_repo.get_by_role(
            verification_id, AgentRole.FIELD.value
        )
        return TaskState(task.state) if task else None

    # ─── Outcomes ─────────────────────────────────────────────────

    async def understood(self, session: AssistantSession, text: str) -> BotReply:
        """A turn the assistant handled — resets the §26.6.2 consecutive-miss counter."""
        await self._sessions.note_understood(session)
        return BotReply(text)

    async def unmatched(self, session: AssistantSession) -> BotReply:
        """A turn the assistant did not understand.

        The first miss re-offers the menu, which is usually all a confused customer
        needs. The second escalates: §26.6.2 draws the line at two, and guessing a third
        time is how a bot talks someone out of the product.
        """
        should_escalate = await self._sessions.note_unmatched(session)
        if should_escalate:
            return await self.escalate(EscalationReason.UNMATCHED_INTENTS)
        return BotReply("Sorry, I didn't quite get that.\n\n" + content.menu())

    async def escalate(self, reason: EscalationReason) -> BotReply:
        return BotReply(content.escalation(reason, await self._coverage()), reason)

    async def _coverage(self) -> Coverage:
        return await self._support_hours_service.coverage()

    async def _alert_admins(self, conversation: Conversation, session: AssistantSession) -> None:
        """Tell the console a conversation now needs a person (§26.6.5).

        The customer has already been answered, so this is operational rather than
        urgent — in-app only, per the notification rule. Best-effort by construction:
        this runs inside the failure handler, and an alert that raised would turn a
        recovered turn into an unrecovered one.
        """
        try:
            admins = await self._user_repo.list_admins()
            if not admins:
                return
            await publish_domain_event(
                DomainEvent(
                    type=EventType.BOT_PIPELINE_FAILED,
                    recipient_user_ids=tuple(str(admin.id) for admin in admins),
                    data={
                        "conversation_id": Utils.uuid_to_hex(conversation.id),
                        "phone_e164": session.phone_e164,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.error(f"Could not raise an assistant-failure alert: {exc}")
