"""The bot engine — one inbound message in, one reply out (PRD §7.6, WA-11/WA-14/WA-39).

This is the dispatcher, and dispatch order *is* the safety model. Every turn runs the same
gauntlet, and each gate exists because skipping it produces a specific failure:

1. **Is a human already on this thread?** (D57) The bot stays silent. Talking over an
   agent is the failure customers notice most.
2. **Does this turn owe a welcome?** (§7.6.1) First contact, or 30 days idle — the bot
   discloses what it is and repeats the payment pledge before anything else.
3. **Do the customer's own words hit a guardrail?** (§7.6.4) Checked *before* any
   classification, deterministically, so no model — wrong, slow, or jailbroken — can talk
   the bot into rendering a verdict.
4. **What did they mean?** Only now is the classifier consulted, and only to pick a flow.
5. **Does the intent itself escalate?** (§7.6.2) Judgments, refunds, and asking for a
   person are recognisable but never answerable.
6. **Is this a WhatsApp capability at all?** (§7.3.4) Otherwise: handoff, or a redirect.
7. **Did we understand?** Two consecutive misses route to a human rather than guess again.

And wrapping all of it: **anything that raises becomes a warm handover** (§7.6.5). A bot
that goes quiet is indistinguishable from a scam that stopped replying, so an outage
answers with an apology and a person — never with silence.
"""
from __future__ import annotations

import re
from logging import Logger
from typing import List, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus
from main.app.domain.channel.whatsapp.bot import content, guardrails
from main.app.domain.channel.whatsapp.bot.capabilities import (
    ChannelAction,
    ChannelCapability,
    capability_for,
    handoff_intent_for,
)
from main.app.domain.channel.whatsapp.bot.flows import handoff as handoff_flow
from main.app.domain.channel.whatsapp.bot.flows import intake as intake_flow
from main.app.domain.channel.whatsapp.bot.flows import media as media_flow
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.projection import channel_state
from main.app.domain.channel.whatsapp.bot.reply import BotReply
from main.app.domain.channel.whatsapp.bot.sender import WhatsAppBotSender
from main.app.domain.channel.whatsapp.bot.session.models import (
    BotFlow,
    BotMode,
    EscalationReason,
    WhatsAppBotSession,
)
from main.app.domain.channel.whatsapp.bot.session.service import WhatsAppBotSessionService
from main.app.domain.channel.whatsapp.bot.support_hours import Coverage, SupportHoursService
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentSource
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.app.domain.verification.delegate.service import CaseDelegateService
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
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    InboundWhatsAppMessage,
)

logger: Logger = di["logger"]

# How many of a customer's cases a status disambiguation will offer. A WhatsApp message
# listing fifteen properties is unreadable; someone with more than this has a dashboard.
_MAX_CASES_OFFERED = 5

# Menu positions (§7.6.1). The welcome offers numbers, so the numbers have to mean
# something on the next turn — a customer replying "3" to a numbered menu and being told
# the bot did not understand is the most avoidable miss in the whole channel.
_MENU_CHOICES = {
    "1": BotIntent.LEARN,
    "2": BotIntent.START_VERIFICATION,
    "3": BotIntent.CHECK_STATUS,
    "4": BotIntent.TALK_TO_HUMAN,
    "5": BotIntent.PRICING,
}

# The keyword-only intents (D64, §7.4.3), matched on the customer's literal words before
# the classifier runs. They are deliberately outside the classifier's vocabulary: a model
# must not revoke someone's consent or claim a case by inference.
#
# Meta and the customer both treat STOP as binding, so it must never be answered with
# "I didn't understand" — and never with "a person will get back to you" either, because
# an opt-out that waits for the next working day is not an opt-out. D64 fixes the two
# vocabularies: the STOP set revokes **both** §7.4.6 consents, the START set restores
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

# What the closing message invites the customer to say when their 15-minute link has
# expired. Literal phrases, not a classified intent: this is the payment path, and it must
# answer identically every time.
_RESEND_LINK_PHRASES = {
    "pay", "link", "new link", "fresh link", "send the link", "send link",
    "resend", "resend link", "another link", "expired",
}

# `VP-2026-0001` — the case reference a customer is handed on every receipt and report.
_CASE_REFERENCE = re.compile(r"\bVP-\d{4}-\d{3,}\b", re.IGNORECASE)

# Which action each intent is asking for, so §7.3.4 is consulted once per turn rather
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

# The §7.3.4 handoff a parked "which case?" question is waiting on. Both directions are
# needed: the action picks the flow when the question is asked, and the flow picks the
# action back up when the customer answers a turn later.
_HANDOFF_FLOWS: dict[ChannelAction, BotFlow] = {
    ChannelAction.PAY: BotFlow.PAY,
    ChannelAction.VIEW_REPORT: BotFlow.REPORT,
}
_HANDOFF_ACTIONS: dict[BotFlow, ChannelAction] = {
    flow: action for action, flow in _HANDOFF_FLOWS.items()
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppBotEngine:
    def __init__(
        self,
        whatsapp_bot_session_service: WhatsAppBotSessionService,
        whatsapp_bot_sender: WhatsAppBotSender,
        whatsapp_link_service: WhatsAppLinkService,
        whatsapp_consent_service: WhatsAppConsentService,
        case_delegate_service: CaseDelegateService,
        intent_service: IntentService,
        support_hours_service: SupportHoursService,
        pricing_config_service: PricingConfigService,
        verification_repo: VerificationRepo,
        verification_task_repo: VerificationTaskRepo,
        property_service: PropertyService,
        user_repo: UserRepo,
        handoff_token_service: HandoffTokenService,
    ):
        self._whatsapp_bot_session_service = whatsapp_bot_session_service
        self._whatsapp_bot_sender = whatsapp_bot_sender
        self._whatsapp_link_service = whatsapp_link_service
        self._whatsapp_consent_service = whatsapp_consent_service
        self._case_delegate_service = case_delegate_service
        self._intent_service = intent_service
        self._support_hours_service = support_hours_service
        self._pricing_config_service = pricing_config_service
        self._verification_repo = verification_repo
        self._verification_task_repo = verification_task_repo
        self._property_service = property_service
        self._user_repo = user_repo
        self._handoff_token_service = handoff_token_service

    async def handle(
        self, message: InboundWhatsAppMessage, conversation: Conversation
    ) -> Optional[BotReply]:
        """Answer one inbound message, or stay silent when a human owns the thread.

        Returns the reply that was sent, which is what the drive-through and the §7.6.4
        suite assert on. `None` means the bot deliberately said nothing.
        """
        session = await self._whatsapp_bot_session_service.get_or_open(message.from_phone)
        if session.mode == BotMode.HUMAN.value:
            # D57: sticky until someone hands back from the console.
            return None

        try:
            reply = await self._decide(message, session)
        except Exception as exc:  # noqa: BLE001 — §7.6.5: never go quiet
            logger.exception(f"Bot turn failed for {message.from_phone}: {exc}")
            reply = BotReply(
                content.failure_fallback(await self._coverage()),
                EscalationReason.PIPELINE_FAILURE,
            )
            await self._alert_admins(session)

        if reply.is_escalation:
            await self._whatsapp_bot_session_service.note_escalation(
                session, reply.escalation_reason
            )
        await self._whatsapp_bot_sender.reply(conversation, session.phone_e164, reply.text)
        return reply

    # ─── The gauntlet ─────────────────────────────────────────────

    async def _decide(
        self, message: InboundWhatsAppMessage, session: WhatsAppBotSession
    ) -> BotReply:
        welcome_due = await self._whatsapp_bot_session_service.record_inbound(session)
        if welcome_due:
            # The welcome answers the turn on its own. A customer's first message is
            # usually "hi", and a bot that greeted *and* answered would bury the
            # disclosure and the payment pledge under a wall of text.
            return BotReply(content.welcome())

        # §7.6.3 owns any non-text turn, caption or not. It runs before the guardrails
        # because a caption is not what is being answered — the *thing that arrived* is,
        # and the three answers §7.6.3 gives are all safe ones (an acknowledgment, a
        # handover, or a link to the customer's own upload page).
        if media_flow.is_media(message.kind):
            return await self._media(session, message.kind)

        text = (message.text or "").strip()
        if not text:
            return await self._unmatched(session)

        verdict = guardrails.check_message(text)
        if verdict:
            return await self._escalate(verdict.reason)

        # A parked flow reads the message in its own context before anything else — the
        # customer is answering the question the bot just asked.
        parked = await self._resume_flow(session, text)
        if parked:
            return parked

        # A finished intake whose link has probably expired. Matched on the customer's
        # literal words rather than by classification: the closing message told them to
        # say this, and a money path should answer the same way every time.
        if self._wants_a_fresh_link(session, text):
            return await self._resend_intake_link(session)

        intent = await self._classify(text)
        verdict = guardrails.check_intent(intent)
        if verdict:
            return await self._escalate(verdict.reason)

        return await self._route(session, intent, text)

    async def _classify(self, text: str) -> BotIntent:
        """Menu numbers first, then the classifier.

        The menu is deterministic and the classifier is not, so a customer who replies
        with a number gets the same answer every time — and a model outage cannot break
        the one path the welcome explicitly invited them to use.
        """
        message = text.strip()
        choice = _MENU_CHOICES.get(message)
        if choice:
            return choice
        keyword = _KEYWORD_INTENTS.get(message.lower())
        if keyword:
            return keyword
        if _CASE_REFERENCE.search(message):
            # The customer quoted a case reference. That is a literal fact about the
            # message, not an inference, so it outranks whatever the classifier makes
            # of the surrounding words.
            return BotIntent.CONTINUE_CASE
        result = await self._intent_service.classify(text)
        return result.intent

    async def _route(
        self, session: WhatsAppBotSession, intent: BotIntent, text: str
    ) -> BotReply:
        action = _INTENT_ACTIONS.get(intent)
        if action and capability_for(action) == ChannelCapability.NOT_OFFERED:
            return BotReply(content.account_management_not_offered())

        if intent == BotIntent.MENU:
            return await self._understood(session, content.menu())
        if intent == BotIntent.LEARN:
            topic = content.faq_topic_for(text)
            answer = content.faq_answer(topic) if topic else content.learn()
            return await self._understood(session, answer)
        if intent == BotIntent.PRICING:
            view = await self._pricing_config_service.view()
            return await self._understood(session, content.pricing(view))
        if intent == BotIntent.CHECK_STATUS:
            return await self._status(session)
        if intent == BotIntent.LINK_ACCOUNT:
            # S4 owns the linking flow itself; here the bot only points at it, which is
            # also the right answer for an unlinked number asking about a case.
            return await self._understood(session, content.unlinked_number())
        if intent == BotIntent.STOP_MESSAGES:
            return await self._stop_messages(session)
        if intent == BotIntent.START_MESSAGES:
            return await self._start_messages(session)
        if intent == BotIntent.CONTINUE_CASE:
            return await self._continue_case(session, text)
        if intent == BotIntent.START_VERIFICATION:
            return await self._begin_intake(session)
        if action in _HANDOFF_FLOWS:
            return await self._handoff(session, action)

        return await self._unmatched(session)

    # ─── Messaging consent (§7.4.6, D64) ──────────────────────────
    #
    # Handled by the bot, in one turn, always. These two intents are keyword-only —
    # excluded from `CLASSIFIABLE_INTENTS` — so a model can never revoke someone's consent
    # by inference; the customer's literal word is the only thing that reaches here.

    async def _stop_messages(self, session: WhatsAppBotSession) -> BotReply:
        """STOP and its synonyms end **both** §7.4.6 consents (D64)."""
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            # D77: a delegate has no consent row, so their opt-out has to end the
            # delegation — the only lever a non-user has.
            delegate_reply = await self._delegate_stop(session)
            if delegate_reply is not None:
                return delegate_reply
            return await self._understood(
                session, content.messages_stopped_unknown_number()
            )
        await self._whatsapp_consent_service.revoke_all(
            user_id, WhatsAppConsentSource.STOP_KEYWORD
        )
        return await self._understood(session, content.messages_stopped())

    async def _start_messages(self, session: WhatsAppBotSession) -> BotReply:
        """START restores progress updates only; marketing needs the web (D64)."""
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            # Nothing to restore, and the linking invitation is the honest next step —
            # updates about a case require an account to have a case on.
            return await self._understood(session, content.unlinked_number())
        await self._whatsapp_consent_service.grant_utility(
            user_id, WhatsAppConsentSource.START_KEYWORD
        )
        return await self._understood(session, content.messages_restarted())

    # ─── Delegates (§7.4.5, D67) ──────────────────────────────────

    async def _delegate_status(self, session: WhatsAppBotSession) -> Optional[BotReply]:
        """The status reply for an authorized delegate, or ``None`` if this is not one.

        Asked only after `resolve_user_for_phone` has answered `None`, so this never
        overrides an account. It reads the one case the delegation names — never the
        customer's list — and the reply carries no report link, because
        `render_for_delegate` has no path to one.
        """
        delegate = await self._case_delegate_service.resolve_delegate_for_phone(
            session.phone_e164
        )
        if delegate is None:
            return None
        case = await self._load_case(delegate.verification_id)
        if case is None:
            # The delegation outlived its verification. Nothing to report, and inventing
            # a status would be worse than treating them as a new enquiry.
            return None
        await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(
            session, status_flow.render_for_delegate(case, delegate.name).text
        )

    async def _delegate_stop(self, session: WhatsAppBotSession) -> Optional[BotReply]:
        """Honour STOP from a number that is a delegate and nothing else (D77).

        A delegate has no consent row, so ending the delegation is the only lever that
        actually stops the messages — and a STOP we acknowledge but do not act on is the
        kind of thing Meta's quality rating is built to notice.
        """
        delegate = await self._case_delegate_service.revoke_by_phone(session.phone_e164)
        if delegate is None:
            return None
        return await self._understood(session, content.messages_stopped_unknown_number())

    # ─── Status ───────────────────────────────────────────────────

    async def _status(self, session: WhatsAppBotSession) -> BotReply:
        """§7.4.3 — identity first, then the same data the dashboard reads.

        Identity is two questions asked in a fixed order (D67): *whose account is this
        number?*, then *does it hold a delegation?*. The order is the access control — a
        number that is both resolves as the customer, because the account grant is
        strictly wider and reading it as a delegate would lose that person their own data.
        """
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            delegate_reply = await self._delegate_status(session)
            if delegate_reply is not None:
                return delegate_reply
            # One message serves the customer on a second handset and the third party
            # asking about someone else's case: the bot cannot tell them apart, so it
            # names both routes rather than guessing (§7.4.3 + §7.4.5).
            return await self._understood(session, content.unlinked_number())

        cases = await self._load_cases(user_id)
        outcome = status_flow.render(cases)
        if outcome.awaits_choice:
            await self._whatsapp_bot_session_service.enter_flow(
                session, BotFlow.STATUS, context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(session, outcome.text)

    # ─── Non-text inbound (§7.6.3) ────────────────────────────────

    async def _media(self, session: WhatsAppBotSession, kind: InboundKind) -> BotReply:
        """Answer a photo, a document, a voice note or a pin (§7.6.3, WA-06/WA-38).

        Identity first, as everywhere that could touch a case (§7.4.3): an `upload` link
        authorizes writing to one specific verification, so it is only ever issued to a
        number we have proved belongs to the customer who owns that case.
        """
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        cases = await self._load_cases(user_id) if user_id else []
        outcome = media_flow.render(kind, is_linked=bool(user_id), cases=cases)

        if outcome.is_escalation:
            await self._whatsapp_bot_session_service.clear_flow(session)
            return await self._escalate(outcome.escalation_reason)

        if outcome.upload_for_vid:
            await self._whatsapp_bot_session_service.clear_flow(session)
            return await self._understood(
                session, await self._upload_reply(user_id, cases, outcome.upload_for_vid)
            )

        if outcome.awaits_choice:
            await self._whatsapp_bot_session_service.enter_flow(
                session, BotFlow.UPLOAD, context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(session, outcome.text)

    async def _upload_reply(
        self, user_id: str, cases: List[status_flow.CaseSummary], vid: str
    ) -> str:
        """The evidence rule plus a link that writes to exactly one case.

        The token is minted from the *case the bot resolved*, never from anything the
        customer typed: a `vid` is printed on receipts and reports, so accepting one at
        face value would let a forwarded document target someone else's file.
        """
        case = next((c for c in cases if c.vid == vid), None)
        if case is None:
            # The case list changed under us between render and issue. Say the honest
            # thing rather than minting a token for a case we can no longer name.
            return content.document_received_no_case()
        verification = await self._verification_repo.get_by_vid(case.vid)
        if verification is None:
            return content.document_received_no_case()
        token = await self._handoff_token_service.issue(
            user_id, Utils.uuid_to_hex(verification.id), HandoffIntent.UPLOAD
        )
        link = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/wa/upload/{token}"
        return content.document_received_with_link(link)

    async def _resume_upload(
        self, session: WhatsAppBotSession, text: str
    ) -> Optional[BotReply]:
        """The customer picked which case their document belongs to (§7.6.3)."""
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            # The link was revoked between the question and the answer — re-run identity
            # rather than issuing a token off a stale offer.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        # Re-filtered, not just re-read: a case that moved out of an uploadable state
        # between the question and the answer must stop being selectable, or the token
        # would be minted for a case the bot would no longer offer.
        cases = [
            case
            for case in media_flow.uploadable_cases(await self._load_cases(user_id))
            if case.vid in offered
        ]
        selected = media_flow.resolve_choice(cases, text)
        if selected is None:
            # Not a choice — the customer moved on. Drop the flow and classify fresh.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(
            session, await self._upload_reply(user_id, cases, selected.vid)
        )

    # ─── Pay and report handoffs (§7.3.4, §7.4.2) ─────────────────

    async def _handoff(
        self, session: WhatsAppBotSession, action: ChannelAction
    ) -> BotReply:
        """Answer "how do I pay?" or "send me my report" with a §7.5 link (WA-17).

        Identity first, as everywhere that could touch a case (§7.4.3): a pay or report
        token names a customer *and* a case, so it is only ever issued to a number we have
        proved belongs to the person whose money — or whose report — is involved.
        """
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        cases = await self._load_cases(user_id) if user_id else []
        outcome = handoff_flow.render(action, is_linked=bool(user_id), cases=cases)

        if outcome.link_for_vid:
            await self._whatsapp_bot_session_service.clear_flow(session)
            return await self._understood(
                session, await self._handoff_reply(action, user_id, cases, outcome.link_for_vid)
            )

        if outcome.awaits_choice:
            await self._whatsapp_bot_session_service.enter_flow(
                session, _HANDOFF_FLOWS[action], context={"vids": list(outcome.offered_vids)}
            )
        else:
            await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(session, outcome.text)

    async def _handoff_reply(
        self,
        action: ChannelAction,
        user_id: str,
        cases: List[status_flow.CaseSummary],
        vid: str,
    ) -> str:
        """Mint the link for exactly one case, and say the right words around it.

        The token is minted from the *case the bot resolved*, never from a reference the
        customer typed — the same rule as the §7.6.3 upload link, and for a sharper reason
        here: a pay link accepted at face value would let a forwarded message send someone
        to pay for a stranger's verification.
        """
        case = next((c for c in cases if c.vid == vid), None)
        if case is None:
            # The case list changed under us between render and issue. Say the honest
            # thing rather than minting a token for a case we can no longer name.
            return handoff_flow.render(action, is_linked=True, cases=[]).text
        verification = await self._verification_repo.get_by_vid(case.vid)
        if verification is None:
            return handoff_flow.render(action, is_linked=True, cases=[]).text

        intent = handoff_intent_for(action)
        token = await self._handoff_token_service.issue(
            user_id, Utils.uuid_to_hex(verification.id), intent
        )
        link = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/wa/{intent.value}/{token}"
        if action == ChannelAction.PAY:
            return content.pay_with_link(link)
        return content.report_with_link(link)

    async def _resume_handoff(
        self, session: WhatsAppBotSession, flow: BotFlow, text: str
    ) -> Optional[BotReply]:
        """The customer picked which case they meant (§7.3.4)."""
        action = _HANDOFF_ACTIONS[flow]
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            # The link was revoked between the question and the answer — re-run identity
            # rather than issuing a token off a stale offer.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        # Re-filtered, not just re-read: a case that stopped being payable — or whose
        # report was pulled — between the question and the answer must stop being
        # selectable, or the token would be minted for a case the bot would no longer offer.
        cases = [
            case
            for case in handoff_flow.eligible_cases(action, await self._load_cases(user_id))
            if case.vid in offered
        ]
        selected = handoff_flow.resolve_choice(cases, text)
        if selected is None:
            # Not a choice — the customer moved on. Drop the flow and classify fresh.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(
            session, await self._handoff_reply(action, user_id, cases, selected.vid)
        )

    async def _resume_flow(
        self, session: WhatsAppBotSession, text: str
    ) -> Optional[BotReply]:
        """Let a parked flow answer, or hand the turn back to normal classification."""
        if session.current_flow == BotFlow.INTAKE.value:
            return await self._continue_intake(session, text)
        if session.current_flow == BotFlow.UPLOAD.value:
            return await self._resume_upload(session, text)
        if session.current_flow in (BotFlow.PAY.value, BotFlow.REPORT.value):
            return await self._resume_handoff(
                session, BotFlow(session.current_flow), text
            )
        if session.current_flow != BotFlow.STATUS.value:
            return None
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            # The link was revoked between the question and the answer. Falling through
            # re-runs the identity check rather than answering from a stale offer.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        offered = (session.context or {}).get("vids") or []
        cases = [case for case in await self._load_cases(user_id) if case.vid in offered]
        outcome = status_flow.render_choice(cases, text)
        if outcome is None:
            # Not a choice — the customer moved on. Drop the flow and classify fresh.
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None
        await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(session, outcome.text)

    # ─── Short-code continuation (§7.4.3, D58) ────────────────────

    async def _continue_case(self, session: WhatsAppBotSession, text: str) -> BotReply:
        """Pick a case up from its reference — "continue VP-2026-0001" (D58).

        Identity first, as everywhere else that touches a case (§7.4.3): quoting a
        reference is not proof of owning it, and the references appear on receipts and
        reports that get forwarded. An unlinked number is offered linking instead, and a
        reference that is not the customer's own is answered as *not found* rather than
        "that is not yours" — confirming a case exists would make the reference space
        probeable.
        """
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
            return await self._understood(session, content.unlinked_number())

        quoted = _CASE_REFERENCE.search(text or "")
        cases = await self._load_cases(user_id)
        match = next(
            (case for case in cases if quoted and case.vid.upper() == quoted.group(0).upper()),
            None,
        )
        if match is None:
            return await self._understood(session, content.case_not_found())

        await self._whatsapp_bot_session_service.clear_flow(session)
        return await self._understood(
            session, status_flow.render([match]).text
        )

    # ─── Intake (§5.1, D69/D70) ───────────────────────────────────

    async def _begin_intake(self, session: WhatsAppBotSession) -> BotReply:
        """Open the four-question intake (§7.3.4 lists it as a full WhatsApp capability).

        No account is required to start: the answers live on the session and identity is
        established at the handoff landing (D69), so a stranger's first message can begin
        a verification.
        """
        outcome = intake_flow.begin()
        await self._park_intake(session, outcome)
        return await self._understood(session, outcome.text)

    async def _continue_intake(
        self, session: WhatsAppBotSession, text: str
    ) -> Optional[BotReply]:
        """Apply one answer. Returns `None` if the customer has left the flow.

        A guardrail hit or an explicit "talk to a human" is handled before this runs, so
        anything reaching here is a genuine attempt at the current question — except a
        message that reads like a different intent entirely, which the abandon check below
        hands back to normal classification rather than forcing into a form.
        """
        if self._is_abandoning_intake(text):
            await self._whatsapp_bot_session_service.clear_flow(session)
            return None

        collected = (session.context or {}).get("intake") or {}
        step = intake_flow.IntakeStep(session.step or 0)
        outcome = intake_flow.answer(step, text, collected, await self._pricing_config_service.view())

        if not outcome.complete:
            await self._park_intake(session, outcome)
            # A re-ask is not a failure to understand the customer — it is the flow doing
            # its job — so it must not count toward the §7.6.2 two-strikes escalation.
            return await self._understood(session, outcome.text)

        return await self._finish_intake(session, outcome)

    async def _finish_intake(
        self, session: WhatsAppBotSession, outcome: intake_flow.IntakeOutcome
    ) -> BotReply:
        """Store the answers and hand off to the website with a single-use link.

        The flow ends here rather than parking at `DONE`: a finished intake left parked
        would read the customer's next message — "thanks", "how long does it take" — as
        another answer and send a second link.
        """
        await self._whatsapp_bot_session_service.retain_intake(session, outcome.collected)
        return await self._understood(session, outcome.text.format(link=await self._intake_link(session)))

    async def _intake_link(self, session: WhatsAppBotSession) -> str:
        token = await self._handoff_token_service.issue_intake(session.phone_e164)
        return f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/wa/intake/{token}"

    async def _resend_intake_link(self, session: WhatsAppBotSession) -> BotReply:
        """Re-issue a link for answers the bot already has (§7.10).

        Worth its own path: the link lasts 15 minutes, §7.10 makes intake→payment the
        channel's headline number, and asking a customer to re-answer four questions
        because they opened their phone late is the easiest conversion to lose.
        """
        link = await self._intake_link(session)
        return await self._understood(
            session,
            "Here's a fresh link to confirm your details and pay:\n"
            f"{link}\n\n"
            f"⚠️ {content.PAYMENT_PLEDGE}",
        )

    async def _park_intake(
        self, session: WhatsAppBotSession, outcome: intake_flow.IntakeOutcome
    ) -> None:
        await self._whatsapp_bot_session_service.enter_flow(
            session, BotFlow.INTAKE, step=int(outcome.step),
            context={"intake": outcome.collected},
        )

    @staticmethod
    def _wants_a_fresh_link(session: WhatsAppBotSession, text: str) -> bool:
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

    async def _load_cases(self, user_id: str) -> List[status_flow.CaseSummary]:
        """The customer's cases, read through the same repo the dashboard list uses.

        §7.3.1's "same API endpoints the website dashboard uses" in practice: the status
        strings come from `tracking/labels.py`, so the two surfaces cannot describe one
        case differently.
        """
        rows, _ = await self._verification_repo.page_for_customer(
            user_id, offset=0, limit=_MAX_CASES_OFFERED
        )
        summaries: List[status_flow.CaseSummary] = []
        for row in rows:
            status = VerificationStatus(row.status)
            summaries.append(
                status_flow.CaseSummary(
                    vid=row.vid,
                    property_label=await self._property_label(row.property_id),
                    status_label=customer_status_label(status),
                    channel_state=channel_state(
                        status, await self._field_task_state(Utils.uuid_to_hex(row.id))
                    ),
                    sla_due_date=row.sla_due_date,
                )
            )
        return summaries

    async def _load_case(self, verification_id: str) -> Optional[status_flow.CaseSummary]:
        """One case, summarised exactly as `_load_cases` summarises the customer's own.

        Keyed by id rather than by customer, because a delegate is granted *this case* and
        has no list to page. Same labels, same projection: a delegate and the buyer read
        the same words for the same state.
        """
        row = await self._verification_repo.get_model(verification_id)
        if row is None:
            return None
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
        `field_inspection` in the §7.3.2 projection."""
        task = await self._verification_task_repo.get_by_role(
            verification_id, AgentRole.FIELD.value
        )
        return TaskState(task.state) if task else None

    # ─── Outcomes ─────────────────────────────────────────────────

    async def _understood(self, session: WhatsAppBotSession, text: str) -> BotReply:
        """A turn the bot handled — resets the §7.6.2 consecutive-miss counter."""
        await self._whatsapp_bot_session_service.note_understood(session)
        return BotReply(text)

    async def _unmatched(self, session: WhatsAppBotSession) -> BotReply:
        """A turn the bot did not understand.

        The first miss re-offers the menu, which is usually all a confused customer
        needs. The second escalates: §7.6.2 draws the line at two, and guessing a third
        time is how a bot talks someone out of the product.
        """
        should_escalate = await self._whatsapp_bot_session_service.note_unmatched(session)
        if should_escalate:
            return await self._escalate(EscalationReason.UNMATCHED_INTENTS)
        return BotReply(
            "Sorry, I didn't quite get that.\n\n" + content.menu()
        )

    async def _escalate(self, reason: EscalationReason) -> BotReply:
        return BotReply(content.escalation(reason, await self._coverage()), reason)

    async def _coverage(self) -> Coverage:
        return await self._support_hours_service.coverage()

    async def _alert_admins(self, session: WhatsAppBotSession) -> None:
        """Tell the console a conversation now needs a person (§7.6.5).

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
                    data={"phone_e164": session.phone_e164},
                )
            )
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.error(f"Could not raise a bot-failure alert: {exc}")
