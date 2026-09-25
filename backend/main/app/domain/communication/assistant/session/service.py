"""Assistant session lifecycle (PRD §26.6.1, §26.6.2, D57, D93).

Everything that changes *where a conversation is* lives here, so the engine can stay a
dispatcher. Five rules are enforced in this one place rather than at each call site:

* A session is created on the assistant's first turn in a conversation and never duplicated
  (the conversation id is unique).
* A human's reply makes the thread sticky-``HUMAN``; only an explicit hand-back releases it
  (D57).
* The welcome fires on first contact and after 30 days idle (§26.6.1) — the same trigger
  that re-states the bot disclosure and the payment pledge.
* The unmatched counter escalates on the second consecutive miss and resets the moment
  the assistant understands something (§26.6.2).
* A web turn waiting for the intent model is marked on the session and claimed by exactly
  one request (D93).

Channel facts (§26.10's WhatsApp analytics, Meta's 24-hour window) are not this service's:
the engine records them through its surface, so a web turn is never counted as WhatsApp
traffic.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.communication.assistant.session.models import (
    UNMATCHED_ESCALATION_THRESHOLD,
    AssistantReadinessDto,
    AssistantSession,
    AssistantSessionDto,
    BotFlow,
    BotMode,
    CreateAssistantSessionDto,
    EscalationReason,
)
from main.app.domain.communication.assistant.session.repo import AssistantSessionRepo
from main.app.domain.communication.conversation.models import Conversation, ConversationChannel
from main.appodus_utils import Utils
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER, IntentProvider
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional


def turn_claim_ttl() -> timedelta:
    """How long a claimed turn is protected before another request may take it over.

    Three intent-model timeouts: the model call is the only slow step, and the SDK retries
    once, so a live turn finishes well inside this. Anything older died mid-turn.
    """
    return timedelta(seconds=3 * settings.INTENT_TIMEOUT_SECONDS)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AssistantSessionService:
    def __init__(self, assistant_session_repo: AssistantSessionRepo):
        self._assistant_session_repo = assistant_session_repo

    async def get_or_open(
        self, conversation: Conversation, phone_e164: Optional[str] = None
    ) -> AssistantSession:
        """The conversation's session, creating it on the assistant's first turn.

        Returns the attached row so the caller can mutate it in the same transaction —
        re-fetching a row created moments earlier is the get-after-create trap.
        """
        existing = await self._assistant_session_repo.get_by_conversation(conversation.id)
        if existing is not None:
            return existing
        session, _ = await self._assistant_session_repo.insert_or_get(
            CreateAssistantSessionDto(
                conversation_id=Utils.uuid_to_hex(conversation.id), phone_e164=phone_e164
            ).model_dump(by_alias=False),
            ["conversation_id"],
        )
        return session

    async def get(self, conversation_id: str) -> Optional[AssistantSession]:
        """This conversation's session, or ``None`` if the assistant never took a turn."""
        return await self._assistant_session_repo.get_by_conversation(conversation_id)

    async def get_by_phone(self, phone_e164: str) -> Optional[AssistantSession]:
        """The WhatsApp conversation's session for a number (an intake link names a number)."""
        return await self._assistant_session_repo.get_by_phone(phone_e164)

    async def take_over(self, conversation: Conversation) -> AssistantSession:
        """A person has joined: the assistant goes quiet until someone hands back (D57).

        Called from the console reply paths rather than from the assistant, because the
        event that matters is a *human* speaking — an escalation the customer never follows
        up on should not silence a thread nobody joined.
        """
        session = await self.get_or_open(conversation, phone_e164=_phone_of(conversation))
        if session.mode != BotMode.HUMAN.value:
            session.mode = BotMode.HUMAN.value
            session.mode_changed_at = Utils.datetime_now()
            # A human is answering, so an in-flight flow is over — and so is a turn still
            # waiting for the model, which would otherwise answer over the agent.
            self._reset_conversation_state(session)
            self._assistant_session_repo.save(session)
        return session

    async def hand_back(self, conversation_id: str) -> Optional[AssistantSession]:
        """Return the thread to the assistant — the explicit half of D57's sticky mode.
        A conversation the assistant never answered has nothing to hand back."""
        session = await self.get(conversation_id)
        if session is None:
            return None
        session.mode = BotMode.BOT.value
        session.mode_changed_at = Utils.datetime_now()
        self._reset_conversation_state(session)
        self._assistant_session_repo.save(session)
        return session

    async def record_inbound(self, session: AssistantSession) -> bool:
        """Stamp the arrival and answer whether this turn owes a welcome (§26.6.1).

        Read before the stamp: `last_inbound_at` is what the idle window is measured
        against, so stamping first would make every returning customer look active. A due
        welcome is also §26.10's definition of an **enquiry**, which the engine records
        through its surface.
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
        self._assistant_session_repo.save(session)
        return welcome_due

    async def note_understood(self, session: AssistantSession) -> None:
        """A turn the assistant handled — the miss counter starts again from zero."""
        if session.unmatched_count:
            session.unmatched_count = 0
            self._assistant_session_repo.save(session)

    async def note_unmatched(self, session: AssistantSession) -> bool:
        """A turn the assistant did not understand. Answers whether that is now an escalation.

        §26.6.2's rule is *consecutive* misses, which is why this counter and
        ``note_understood`` are a pair — either one alone would drift into "two misses
        ever", and a customer who once mistyped would be escalated forever after.
        """
        misses = await self._assistant_session_repo.count_unmatched(session)
        return misses >= UNMATCHED_ESCALATION_THRESHOLD

    async def enter_flow(
        self, session: AssistantSession, flow: BotFlow, step: int = 0, context: Optional[dict] = None
    ) -> None:
        """Park the conversation mid-flow so the next message is read in context."""
        session.current_flow = flow.value
        session.step = step
        session.context = dict(context or {})
        self._assistant_session_repo.save(session)

    async def retain_intake(self, session: AssistantSession, collected: dict) -> None:
        """End the intake flow but keep its answers (§5.1, D69).

        The flow is over — the customer has been sent their link — so leaving it parked
        would make the *next* message, whatever it was, look like another answer and
        re-send the link. But the answers must survive: the landing reads them on
        redemption, and a 15-minute link often needs re-issuing before anyone opens one.
        """
        session.current_flow = None
        session.step = 0
        session.context = {"intake": dict(collected)}
        self._assistant_session_repo.save(session)

    async def clear_flow(self, session: AssistantSession) -> None:
        """Finish a flow. The next message is classified fresh."""
        session.current_flow = None
        session.step = 0
        session.context = None
        self._assistant_session_repo.save(session)

    async def note_escalation(self, session: AssistantSession, reason: EscalationReason) -> None:
        """Record why this conversation went to a human (§26.10).

        The mode is **not** flipped here. The assistant handing off is a request for a
        person; the thread becomes `HUMAN` when one actually replies (D57), so a customer
        whose question no agent has picked up yet still gets answers to their next question
        rather than silence.
        """
        session.last_escalation_reason = reason.value
        session.last_escalated_at = Utils.datetime_now()
        session.current_flow = None
        session.step = 0
        session.unmatched_count = 0
        self._assistant_session_repo.save(session)

    # ── Deferred web turns (D93) ──────────────────────────────────

    async def mark_pending_turn(self, session: AssistantSession, message_id: str) -> None:
        """Leave a turn for the intent model. A newer message replaces an older mark, so
        consecutive messages sent while the model is slow are answered once, as one turn."""
        session.pending_turn_message_id = Utils.uuid_to_hex(message_id)
        session.pending_turn_at = Utils.datetime_now()
        session.turn_claimed_at = None
        self._assistant_session_repo.save(session)

    async def clear_pending_turn(self, session: AssistantSession) -> None:
        """The customer's newest message was answered without the model, so nothing waits."""
        if session.has_pending_turn or session.turn_claimed_at:
            session.pending_turn_message_id = None
            session.pending_turn_at = None
            session.turn_claimed_at = None
            self._assistant_session_repo.save(session)

    async def release_turn(self, session: AssistantSession, message_id: str) -> None:
        """End a claimed turn. The mark is cleared only if it still names the message that was
        answered — a message sent while the model was thinking stays pending for its own turn."""
        if session.pending_turn_message_id == Utils.uuid_to_hex(message_id):
            session.pending_turn_message_id = None
            session.pending_turn_at = None
        session.turn_claimed_at = None
        self._assistant_session_repo.save(session)

    async def pending_conversation_ids(self, conversation_ids: List[str]) -> set[str]:
        return await self._assistant_session_repo.pending_conversation_ids(conversation_ids)

    # ── Console ───────────────────────────────────────────────────

    async def describe(self, conversation: Conversation, enabled: bool) -> AssistantSessionDto:
        """What the console shows beside a thread.

        A thread the assistant has never answered is described as a fresh `BOT` session
        rather than refused: the console asks about whatever thread it is displaying, and
        "no row yet" is the same operational answer as "the assistant is answering".
        """
        conversation_id = Utils.uuid_to_hex(conversation.id)
        if not enabled:
            return AssistantSessionDto(conversation_id=conversation_id, enabled=False)
        window_open = await _window_open(conversation)
        session = await self.get(conversation.id)
        if session is None:
            return AssistantSessionDto(
                conversation_id=conversation_id,
                phone_e164=_phone_of(conversation),
                window_open=window_open,
            )
        return to_assistant_session_dto(session, window_open=window_open)

    async def readiness(self) -> AssistantReadinessDto:
        """§26.11 — whether the channel is configured for live traffic."""
        return AssistantReadinessDto(
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
            human_mode_sessions=await self._assistant_session_repo.count_in_human_mode(),
        )

    @staticmethod
    def _reset_conversation_state(session: AssistantSession) -> None:
        session.current_flow = None
        session.step = 0
        session.unmatched_count = 0
        session.pending_turn_message_id = None
        session.pending_turn_at = None
        session.turn_claimed_at = None


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.INDEPENDENT),
    exclude=["__init__"], exclude_startswith=["_"],
)
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AssistantTurnClaims:
    """Claims a deferred web turn in its **own** committed transaction (D93).

    The claim has to be visible to a concurrent request before the slow model call starts,
    so it cannot ride in the transaction that runs the turn — that one commits only when the
    reply is written, seconds later.
    """

    def __init__(self, assistant_session_repo: AssistantSessionRepo):
        self._assistant_session_repo = assistant_session_repo

    async def claim(self, conversation_id: str) -> Optional[str]:
        """The message id of the turn this request now owns, or ``None``."""
        now = Utils.datetime_now()
        return await self._assistant_session_repo.claim_pending_turn(
            conversation_id, now=now, stale_before=now - turn_claim_ttl()
        )

    async def claimable(self, limit: int, waiting_seconds: Optional[float] = None) -> List[str]:
        """Conversations with a turn left unanswered — the sweep's work list.

        A turn younger than *waiting_seconds* (default: one model timeout) is left to the
        customer's own second request, which is normally already on its way.
        """
        now = Utils.datetime_now()
        grace = settings.INTENT_TIMEOUT_SECONDS if waiting_seconds is None else waiting_seconds
        return await self._assistant_session_repo.list_claimable_turns(
            waiting_before=now - timedelta(seconds=grace),
            stale_before=now - turn_claim_ttl(),
            limit=limit,
        )


def _phone_of(conversation: Conversation) -> Optional[str]:
    if conversation.channel == ConversationChannel.WHATSAPP.value:
        return conversation.external_ref
    return None


async def _window_open(conversation: Conversation) -> Optional[bool]:
    """Meta's 24-hour window — a WhatsApp fact, so ``None`` on any other thread. Resolved at
    call time: the WhatsApp package imports this one."""
    phone = _phone_of(conversation)
    if not phone:
        return None
    from kink import di

    from main.app.domain.channel.whatsapp.window import WhatsAppWindowService

    return await di[WhatsAppWindowService].is_open(phone)


def to_assistant_session_dto(
    session: AssistantSession, *, window_open: Optional[bool] = None
) -> AssistantSessionDto:
    """Map a session row to what the console renders.

    A module-level function rather than a method: `decorate_all_methods` wraps *every*
    method on the service — including a `@staticmethod` — in the transactional and
    tracing decorators, which makes a pure mapper return a coroutine. That failed only at
    runtime, as a 500 on an endpoint whose service call had already succeeded.
    """
    return AssistantSessionDto(
        conversation_id=session.conversation_id,
        phone_e164=session.phone_e164,
        mode=BotMode(session.mode),
        mode_changed_at=session.mode_changed_at,
        current_flow=BotFlow(session.current_flow) if session.current_flow else None,
        last_inbound_at=session.last_inbound_at,
        window_open=window_open,
        last_escalation_reason=(
            EscalationReason(session.last_escalation_reason)
            if session.last_escalation_reason
            else None
        ),
        last_escalated_at=session.last_escalated_at,
    )
