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

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus
from main.app.domain.channel.whatsapp.bot import content, guardrails
from main.app.domain.channel.whatsapp.bot.capabilities import (
    ChannelAction,
    ChannelCapability,
    capability_for,
)
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
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
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
# "I didn't understand". The flows that honour these land in S6 (continuation) and S8
# (consent); until then they route to a person, which is a promise we can actually keep.
_KEYWORD_INTENTS = {
    "stop": BotIntent.STOP_MESSAGES,
    "unsubscribe": BotIntent.STOP_MESSAGES,
    "cancel messages": BotIntent.STOP_MESSAGES,
    "start": BotIntent.START_MESSAGES,
    "resume": BotIntent.START_MESSAGES,
}

# `VP-2026-0001` — the case reference a customer is handed on every receipt and report.
_CASE_REFERENCE = re.compile(r"\bVP-\d{4}-\d{3,}\b", re.IGNORECASE)

# Inbound kinds the bot cannot read (§7.6.3). Documents and images are handled by the
# upload handoff rather than escalated, so they are deliberately absent.
_UNREADABLE_KINDS = frozenset(
    {InboundKind.AUDIO, InboundKind.LOCATION, InboundKind.CONTACTS, InboundKind.UNSUPPORTED}
)

# Which action each intent is asking for, so §7.3.4 is consulted once per turn rather
# than remembered per flow.
_INTENT_ACTIONS = {
    BotIntent.LEARN: ChannelAction.LEARN,
    BotIntent.PRICING: ChannelAction.LEARN,
    BotIntent.START_VERIFICATION: ChannelAction.START_INTAKE,
    BotIntent.CHECK_STATUS: ChannelAction.CHECK_STATUS,
    BotIntent.TALK_TO_HUMAN: ChannelAction.TALK_TO_HUMAN,
    BotIntent.LINK_ACCOUNT: ChannelAction.CHECK_STATUS,
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
        intent_service: IntentService,
        support_hours_service: SupportHoursService,
        pricing_config_service: PricingConfigService,
        verification_repo: VerificationRepo,
        verification_task_repo: VerificationTaskRepo,
        property_service: PropertyService,
        user_repo: UserRepo,
    ):
        self._whatsapp_bot_session_service = whatsapp_bot_session_service
        self._whatsapp_bot_sender = whatsapp_bot_sender
        self._whatsapp_link_service = whatsapp_link_service
        self._intent_service = intent_service
        self._support_hours_service = support_hours_service
        self._pricing_config_service = pricing_config_service
        self._verification_repo = verification_repo
        self._verification_task_repo = verification_task_repo
        self._property_service = property_service
        self._user_repo = user_repo

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

        if message.kind in _UNREADABLE_KINDS:
            return await self._escalate(EscalationReason.UNSUPPORTED_MEDIA)

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
        if intent in (BotIntent.STOP_MESSAGES, BotIntent.START_MESSAGES):
            # D64's consent ledger lands in S8. A person can honour the request today;
            # a bot that replied "I didn't understand" to STOP could not.
            return await self._escalate(EscalationReason.CAPABILITY_NOT_OFFERED)
        if intent == BotIntent.CONTINUE_CASE:
            # S6 resumes the case itself. Until then the reference is at least recognised
            # and answered with what the bot *can* say about it.
            return await self._status(session)
        if intent == BotIntent.START_VERIFICATION:
            # Intake is a §7.3.4 `FULL` capability, but its flow lands in S6. Until then
            # the honest answer is a person, counted as an unmatched-capability
            # escalation rather than silently pretended away.
            return await self._escalate(EscalationReason.CAPABILITY_NOT_OFFERED)

        return await self._unmatched(session)

    # ─── Status ───────────────────────────────────────────────────

    async def _status(self, session: WhatsAppBotSession) -> BotReply:
        """§7.4.3 — identity first, then the same data the dashboard reads."""
        user_id = await self._whatsapp_link_service.resolve_user_for_phone(session.phone_e164)
        if not user_id:
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

    async def _resume_flow(
        self, session: WhatsAppBotSession, text: str
    ) -> Optional[BotReply]:
        """Let a parked flow answer, or hand the turn back to normal classification."""
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
