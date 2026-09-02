"""Bot session lifecycle (PRD §7.6.1, §7.6.2, D57).

Everything that changes *where a conversation is* lives here, so the engine can stay a
dispatcher. Four rules are enforced in this one place rather than at each call site:

* A session is created on first contact and never duplicated (the number is unique).
* An agent's reply makes the thread sticky-``HUMAN``; only an explicit hand-back releases
  it (D57).
* The welcome fires on first contact and after 30 days idle (§7.6.1) — the same trigger
  that re-states the bot disclosure and the payment pledge.
* The unmatched counter escalates on the second consecutive miss and resets the moment
  the bot understands something (§7.6.2).
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.bot.session.models import (
    UNMATCHED_ESCALATION_THRESHOLD,
    BotChannelReadinessDto,
    BotFlow,
    BotMode,
    BotSessionDto,
    CreateWhatsAppBotSessionDto,
    EscalationReason,
    WhatsAppBotSession,
)
from main.app.domain.channel.whatsapp.bot.session.repo import WhatsAppBotSessionRepo
from main.appodus_utils import Utils
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER, IntentProvider
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_e164


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppBotSessionService:
    def __init__(self, whatsapp_bot_session_repo: WhatsAppBotSessionRepo):
        self._whatsapp_bot_session_repo = whatsapp_bot_session_repo

    async def get_or_open(self, phone: str) -> WhatsAppBotSession:
        """The session for *phone*, creating it on first contact.

        Returns the attached row so the caller can mutate it in the same transaction —
        re-fetching a row created moments earlier is the get-after-create trap.
        """
        normalized = to_e164(phone)
        existing = await self._whatsapp_bot_session_repo.get_by_phone(normalized)
        if existing is not None:
            return existing
        return await self._whatsapp_bot_session_repo.create_return_model(
            CreateWhatsAppBotSessionDto(phone_e164=normalized)
        )

    async def get(self, phone: str) -> Optional[WhatsAppBotSession]:
        """This number's session, or ``None`` if it has never written to us."""
        return await self._whatsapp_bot_session_repo.get_by_phone(to_e164(phone))

    async def take_over(self, phone: str) -> WhatsAppBotSession:
        """An agent has joined: the bot goes quiet until someone hands back (D57).

        Called from the console reply path rather than from the bot, because the event
        that matters is a *human* speaking — an escalation the customer never follows up
        on should not silence a thread nobody joined.
        """
        session = await self.get_or_open(phone)
        if session.mode != BotMode.HUMAN.value:
            session.mode = BotMode.HUMAN.value
            session.mode_changed_at = Utils.datetime_now()
            # A human is answering, so an in-flight bot flow is over. Leaving it set
            # would resume mid-flow on hand-back, minutes or days after its context
            # stopped being true.
            session.current_flow = None
            session.step = 0
            session.unmatched_count = 0
            self._whatsapp_bot_session_repo.save(session)
        return session

    async def hand_back(self, phone: str) -> WhatsAppBotSession:
        """Return the thread to the bot — the explicit half of D57's sticky mode."""
        session = await self.get_or_open(phone)
        session.mode = BotMode.BOT.value
        session.mode_changed_at = Utils.datetime_now()
        session.current_flow = None
        session.step = 0
        session.unmatched_count = 0
        self._whatsapp_bot_session_repo.save(session)
        return session

    async def record_inbound(self, session: WhatsAppBotSession) -> bool:
        """Stamp the arrival and answer whether this turn owes a welcome (§7.6.1).

        Read before the stamp: `last_inbound_at` is what the idle window is measured
        against, so stamping first would make every returning customer look active.
        """
        now = Utils.datetime_now()
        welcome_due = session.is_welcome_due(now)
        session.last_inbound_at = now
        if welcome_due:
            session.welcomed_at = now
            # The welcome is a one-shot answer, so it leaves no flow behind — and
            # clearing wipes any flow the customer abandoned before the 30-day gap.
            # Resuming a month-old half-finished intake would be worse than starting
            # over: the property they were asking about has very likely moved on.
            session.current_flow = None
            session.step = 0
            session.context = None
        self._whatsapp_bot_session_repo.save(session)
        return welcome_due

    async def note_understood(self, session: WhatsAppBotSession) -> None:
        """A turn the bot handled — the miss counter starts again from zero."""
        if session.unmatched_count:
            session.unmatched_count = 0
            self._whatsapp_bot_session_repo.save(session)

    async def note_unmatched(self, session: WhatsAppBotSession) -> bool:
        """A turn the bot did not understand. Answers whether that is now an escalation.

        §7.6.2's rule is *consecutive* misses, which is why this counter and
        ``note_understood`` are a pair — either one alone would drift into "two misses
        ever", and a customer who once mistyped would be escalated forever after.
        """
        session.unmatched_count = (session.unmatched_count or 0) + 1
        self._whatsapp_bot_session_repo.save(session)
        return session.unmatched_count >= UNMATCHED_ESCALATION_THRESHOLD

    async def enter_flow(
        self, session: WhatsAppBotSession, flow: BotFlow, step: int = 0, context: Optional[dict] = None
    ) -> None:
        """Park the conversation mid-flow so the next message is read in context."""
        session.current_flow = flow.value
        session.step = step
        session.context = dict(context or {})
        self._whatsapp_bot_session_repo.save(session)

    async def retain_intake(self, session: WhatsAppBotSession, collected: dict) -> None:
        """End the intake flow but keep its answers (§5.1, D69).

        The flow is over — the customer has been sent their link — so leaving it parked
        would make the *next* message, whatever it was, look like another answer and
        re-send the link. But the answers must survive: the landing reads them on
        redemption, and a 15-minute link often needs re-issuing before anyone opens one.
        """
        session.current_flow = None
        session.step = 0
        session.context = {"intake": dict(collected)}
        self._whatsapp_bot_session_repo.save(session)

    async def clear_flow(self, session: WhatsAppBotSession) -> None:
        """Finish a flow. The next message is classified fresh."""
        session.current_flow = None
        session.step = 0
        session.context = None
        self._whatsapp_bot_session_repo.save(session)

    async def note_escalation(
        self, session: WhatsAppBotSession, reason: EscalationReason
    ) -> None:
        """Record why this conversation went to a human (§7.10).

        The mode is **not** flipped here. The bot handing off is a request for a person;
        the thread becomes `HUMAN` when one actually replies (D57), so a customer whose
        question no agent has picked up yet still gets bot answers to their next question
        rather than silence.
        """
        session.last_escalation_reason = reason.value
        session.last_escalated_at = Utils.datetime_now()
        session.current_flow = None
        session.step = 0
        session.unmatched_count = 0
        self._whatsapp_bot_session_repo.save(session)

    async def describe(self, phone: str) -> BotSessionDto:
        """What the console shows beside a thread.

        A number that has never written to us is described as a fresh `BOT` session
        rather than refused: the console asks about whatever thread it is displaying,
        and "no row yet" is the same operational answer as "the bot is answering".
        """
        session = await self.get(phone)
        if session is None:
            return BotSessionDto(phone_e164=to_e164(phone), mode=BotMode.BOT)
        return to_bot_session_dto(session)

    async def readiness(self) -> BotChannelReadinessDto:
        """§7.11 — whether the channel is configured for live traffic."""
        return BotChannelReadinessDto(
            whatsapp_provider=settings.WHATSAPP_PROVIDER.value,
            intent_provider=settings.INTENT_PROVIDER.value,
            intent_model=settings.INTENT_MODEL,
            # The stub needs no key and is fully configured without one, so it is ready
            # by definition — reporting it as unconfigured would make every CI and local
            # run look broken.
            intent_configured=(
                settings.INTENT_PROVIDER == IntentProvider.STUB
                or bool(settings.INTENT_API_KEY)
                and settings.INTENT_API_KEY != SECRET_PLACEHOLDER
            ),
            human_mode_sessions=await self._whatsapp_bot_session_repo.count_in_human_mode(),
        )


def to_bot_session_dto(session: WhatsAppBotSession) -> BotSessionDto:
    """Map a session row to what the console renders.

    A module-level function rather than a method: `decorate_all_methods` wraps *every*
    method on the service — including a `@staticmethod` — in the transactional and
    tracing decorators, which makes a pure mapper return a coroutine. That failed only at
    runtime, as a 500 on an endpoint whose service call had already succeeded.
    """
    return BotSessionDto(
        phone_e164=session.phone_e164,
        mode=BotMode(session.mode),
        mode_changed_at=session.mode_changed_at,
        current_flow=BotFlow(session.current_flow) if session.current_flow else None,
        last_inbound_at=session.last_inbound_at,
        last_escalation_reason=(
            EscalationReason(session.last_escalation_reason)
            if session.last_escalation_reason
            else None
        ),
        last_escalated_at=session.last_escalated_at,
    )
