"""The assistant in the portal (PRD §16.7, D93).

What is defended here is the shape that makes a web turn safe on serverless hosts:

* the deterministic steps answer **inside the customer's send**, and only a turn that needs
  the intent model is left pending — never both, never neither;
* a pending turn is answered by **exactly one** request, and a message sent while the model
  was thinking keeps its own turn;
* the assistant talks to the thread's owner, derived from the thread — never the caller —
  and on a case's own thread that case is pinned;
* the portal surface links straight to portal pages, posts an in-app reply, and counts
  nothing as WhatsApp traffic.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.assistant.capabilities import ChannelAction
from main.app.domain.communication.assistant.engine import AssistantEngine, TurnResult
from main.app.domain.communication.assistant.reply import BotReply
from main.app.domain.communication.assistant.session.models import AssistantSession, BotMode
from main.app.domain.communication.assistant.session.service import AssistantSessionService
from main.app.domain.communication.assistant.surface import (
    AssistantMessage,
    AssistantParty,
    AssistantSurfaceKind,
    assistant_surface_for,
)
from main.app.domain.communication.assistant.web import WebAssistantService, WebAssistantSurface
from main.app.domain.communication.chat_message.models import MessageKind, MessageSource, SenderKind
from main.app.domain.communication.conversation.models import ConversationChannel, ConversationType
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult
from main.appodus_utils.config.settings import IntentProvider

CUSTOMER = "11111111-1111-1111-1111-111111111111"
CONVERSATION = "c0ffee00000000000000000000000001"
MESSAGE = "a11ce000000000000000000000000001"


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _conversation(type_=ConversationType.GENERAL_SUPPORT, channel=ConversationChannel.WEB, **overrides):
    values = dict(
        id=CONVERSATION, type=type_.value, channel=channel.value, created_by=CUSTOMER,
        verification_id=None, external_ref=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _message(**overrides):
    values = dict(
        id=MESSAGE, body="How much is it?", sender_kind=SenderKind.CUSTOMER.value,
        sender_user_id=CUSTOMER, state=ChatMessageState.DELIVERED.value,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _session_row(**overrides) -> AssistantSession:
    row = AssistantSession()
    row.conversation_id = CONVERSATION
    row.mode = BotMode.BOT.value
    row.pending_turn_message_id = None
    row.pending_turn_at = None
    row.turn_claimed_at = None
    for field, value in overrides.items():
        setattr(row, field, value)
    return row


def _service(*, first=TurnResult(), second=TurnResult(), session=None, claim=None, verification=None):
    svc = object.__new__(WebAssistantService)
    svc._engine = MagicMock(
        answer_without_model=AsyncMock(return_value=first),
        answer_with_model=AsyncMock(return_value=second),
    )
    svc._surface = MagicMock()
    row = session if session is not None else _session_row()
    real_sessions = object.__new__(AssistantSessionService)
    real_sessions._assistant_session_repo = MagicMock(save=MagicMock())
    svc._sessions = MagicMock(
        get=AsyncMock(return_value=row),
        mark_pending_turn=AsyncMock(side_effect=real_sessions.mark_pending_turn),
        clear_pending_turn=AsyncMock(side_effect=real_sessions.clear_pending_turn),
        release_turn=AsyncMock(side_effect=real_sessions.release_turn),
    )
    svc._claims = MagicMock(claim=AsyncMock(return_value=claim))
    svc._conversations = MagicMock(get_model=AsyncMock(return_value=_conversation()))
    svc._messages = MagicMock(get_model=AsyncMock(return_value=_message(body="what's a survey plan?")))
    svc._verifications = MagicMock(get_model=AsyncMock(return_value=verification))
    return svc, row


class TestWhichThreadsTheAssistantAnswers:
    @pytest.mark.parametrize("type_, channel, expected", [
        (ConversationType.GENERAL_SUPPORT, ConversationChannel.WEB, AssistantSurfaceKind.WEB),
        (ConversationType.CUSTOMER_ADMIN, ConversationChannel.WEB, AssistantSurfaceKind.WEB),
        (ConversationType.ADMIN_AGENT, ConversationChannel.WEB, None),
        (ConversationType.GENERAL_SUPPORT, ConversationChannel.WHATSAPP, AssistantSurfaceKind.WHATSAPP),
    ])
    def test_the_surface_follows_the_thread(self, type_, channel, expected):
        """Staff talking to staff is never answered, and a WhatsApp thread is answered on
        WhatsApp — never by a portal reply to a phone the customer is not holding."""
        assert assistant_surface_for(_conversation(type_, channel)) == expected


class TestPhaseOneInsideTheSend:
    async def test_a_deterministic_answer_is_returned_with_the_send(self):
        reply_message = SimpleNamespace(id="reply-1")
        svc, row = _service(first=TurnResult(reply=BotReply("₦5,000"), delivered=_as_chat_message(reply_message)))

        outcome = await svc.after_customer_message(_conversation(), _message(body="5"))

        assert outcome.reply is not None and outcome.pending is False
        assert row.pending_turn_message_id is None

    async def test_a_turn_that_needs_the_model_is_left_pending_not_answered(self):
        svc, row = _service(first=TurnResult(needs_model=True))

        outcome = await svc.after_customer_message(_conversation(), _message())

        assert outcome.pending is True and outcome.reply is None
        assert row.pending_turn_message_id == MESSAGE
        svc._engine.answer_with_model.assert_not_awaited()

    async def test_a_newer_answered_message_clears_an_older_pending_turn(self):
        """The customer moved on; answering the stale question afterwards would read as the
        assistant replying to the wrong message."""
        svc, row = _service(
            first=TurnResult(reply=BotReply("menu")),
            session=_session_row(pending_turn_message_id="0ld", turn_claimed_at=Utils.datetime_now()),
        )

        await svc.after_customer_message(_conversation(), _message(body="menu"))

        assert row.pending_turn_message_id is None and row.turn_claimed_at is None

    @pytest.mark.parametrize("message, conversation", [
        (_message(state=ChatMessageState.HELD.value), _conversation()),
        (_message(sender_kind=SenderKind.ADMIN.value), _conversation()),
        (_message(), _conversation(ConversationType.ADMIN_AGENT)),
        (_message(), _conversation(channel=ConversationChannel.WHATSAPP)),
        (_message(sender_user_id="someone-else"), _conversation()),
    ], ids=["held-by-the-fraud-scan", "an-admin-wrote-it", "staff-thread", "whatsapp-thread", "not-the-owner"])
    async def test_the_assistant_stays_out_of_what_it_does_not_answer(self, message, conversation):
        svc, _row = _service(first=TurnResult(reply=BotReply("hello")))

        outcome = await svc.after_customer_message(conversation, message)

        assert outcome.reply is None and outcome.pending is False
        svc._engine.answer_without_model.assert_not_awaited()

    async def test_on_a_case_thread_the_owner_is_the_cases_customer_and_the_case_is_pinned(self):
        """A case thread's `created_by` is whoever opened it first — often an admin."""
        case = SimpleNamespace(id=Utils.generate_uuid(), customer_id=CUSTOMER)
        svc, _row = _service(first=TurnResult(needs_model=True), verification=case)
        thread = _conversation(ConversationType.CUSTOMER_ADMIN, created_by="admin-1", verification_id="v-1")

        await svc.after_customer_message(thread, _message())

        party = svc._engine.answer_without_model.await_args.args[1]
        assert party == AssistantParty(customer_id=CUSTOMER, pinned_verification_id=Utils.uuid_to_hex(case.id))


class TestPhaseTwoFromTheTurnRequest:
    async def test_a_claimed_turn_is_answered_and_released(self):
        svc, row = _service(
            second=TurnResult(reply=BotReply("A survey plan shows the boundaries.")),
            session=_session_row(pending_turn_message_id=MESSAGE, turn_claimed_at=Utils.datetime_now()),
            claim=MESSAGE,
        )

        outcome = await svc.run_pending_turn(CONVERSATION)

        message = svc._engine.answer_with_model.await_args.args[2]
        assert message == AssistantMessage(text="what's a survey plan?")
        assert row.pending_turn_message_id is None and row.turn_claimed_at is None
        assert outcome.pending is False

    async def test_a_turn_someone_else_holds_is_not_answered_twice(self):
        svc, _row = _service(session=_session_row(pending_turn_message_id=MESSAGE), claim=None)

        outcome = await svc.run_pending_turn(CONVERSATION)

        svc._engine.answer_with_model.assert_not_awaited()
        # Still reported pending, so the client keeps showing the assistant typing.
        assert outcome.pending is True

    async def test_a_message_sent_while_the_model_was_thinking_keeps_its_own_turn(self):
        row = _session_row(pending_turn_message_id=MESSAGE, turn_claimed_at=Utils.datetime_now())

        async def _newer_message_arrives(*_args, **_kwargs):
            row.pending_turn_message_id = "b0b00000000000000000000000000002"
            return TurnResult(reply=BotReply("answer to the first"))

        svc, _ = _service(session=row, claim=MESSAGE)
        svc._engine.answer_with_model = AsyncMock(side_effect=_newer_message_arrives)

        outcome = await svc.run_pending_turn(CONVERSATION)

        assert row.pending_turn_message_id == "b0b00000000000000000000000000002"
        assert row.turn_claimed_at is None
        assert outcome.pending is True


class TestTheSweep:
    async def test_it_claims_turns_exactly_as_a_request_would(self):
        svc, _row = _service(claim=None)
        svc._claims.claimable = AsyncMock(return_value=["c1", "c2"])
        svc.run_pending_turn = AsyncMock(side_effect=[
            SimpleNamespace(reply=object()), SimpleNamespace(reply=None),
        ])

        assert await svc.sweep(waiting_seconds=0) == {"answered": 1}
        svc._claims.claimable.assert_awaited_once_with(20, 0)


class TestThePortalSurface:
    def _surface(self):
        surface = object.__new__(WebAssistantSurface)
        surface._chat = MagicMock(send=AsyncMock(return_value=SimpleNamespace(id="reply-1")))
        surface._sessions = MagicMock(clear_flow=AsyncMock())
        surface._intake_draft_seeder = MagicMock(seed=AsyncMock(return_value="draft-1"))
        return surface

    @pytest.mark.parametrize("action, page", [
        (ChannelAction.PAY, "pay"), (ChannelAction.VIEW_REPORT, "report"),
    ])
    async def test_a_handoff_links_straight_to_the_portal_page(self, action, page, monkeypatch):
        """No `/wa/*` token: the reader is signed in, and the page sits behind their login."""
        from main.app.config.settings import settings

        monkeypatch.setattr(settings, "PUBLIC_APP_BASE_URL", "https://app.example")
        verification = SimpleNamespace(id=Utils.generate_uuid())

        link = await self._surface().link_for(action, AssistantParty(customer_id=CUSTOMER), verification)

        assert link == f"https://app.example/portal/verifications/{Utils.uuid_to_hex(verification.id)}/{page}"

    async def test_a_finished_intake_is_already_the_customers_draft(self):
        surface = self._surface()
        session = _session_row()

        link = await surface.complete_intake(session, AssistantParty(customer_id=CUSTOMER), {"tier": "BASIC"})

        surface._intake_draft_seeder.seed.assert_awaited_once_with(CUSTOMER, {"tier": "BASIC"})
        surface._sessions.clear_flow.assert_awaited_once_with(session)
        assert link.endswith("/portal/verifications/new")

    async def test_a_reply_is_platform_copy_in_the_thread(self):
        surface = self._surface()
        conversation = _conversation()

        await surface.deliver(conversation, BotReply("Hello"))

        args, kwargs = surface._chat.send.await_args
        assert args == (conversation, None, SenderKind.SYSTEM, "Hello")
        assert kwargs == {"kind": MessageKind.SYSTEM_AUTO, "source": MessageSource.WEB}

    async def test_the_portal_counts_nothing_and_offers_no_opt_out_keywords(self):
        surface = self._surface()

        assert surface.handles_consent_keywords is False
        assert await surface.record(MagicMock(), _session_row(), AssistantParty()) is None


class TestTheTwoPhaseSplit:
    """The engine's gate order must be identical whether a turn runs in one request or two."""

    def _engine(self, session, *, intent=BotIntent.PRICING):
        engine = object.__new__(AssistantEngine)
        real = object.__new__(AssistantSessionService)
        real._assistant_session_repo = MagicMock(
            get_by_conversation=AsyncMock(return_value=session), save=MagicMock()
        )
        engine._sessions = real
        engine._intent_service = MagicMock(classify=AsyncMock(
            return_value=IntentResult(intent=intent, confidence=0.9, provider=IntentProvider.STUB)
        ))
        engine._support_hours_service = MagicMock(coverage=AsyncMock(return_value=MagicMock(is_open=True)))
        from main.app.core.state.status import VerificationTier
        from main.app.domain.verification.pricing_config.models import PricingTierDto, TierPricingViewDto

        engine._pricing_config_service = MagicMock(view=AsyncMock(return_value=TierPricingViewDto(
            tiers=[PricingTierDto(tier=VerificationTier.BASIC, price_ngn_minor=5_000_00)]
        )))
        engine._user_repo = MagicMock(list_admins=AsyncMock(return_value=[]))
        surface = object.__new__(WebAssistantSurface)
        surface._chat = MagicMock(send=AsyncMock(return_value=SimpleNamespace(id="reply-1")))
        surface._sessions = real
        return engine, surface

    @staticmethod
    def _welcomed():
        row = _session_row()
        row.welcomed_at = Utils.datetime_now()
        row.last_inbound_at = row.welcomed_at
        row.unmatched_count = 0
        row.step = 0
        row.context = None
        row.current_flow = None
        return row

    async def test_free_text_needs_the_model_and_the_model_is_not_called_in_phase_one(self):
        engine, surface = self._engine(self._welcomed())

        result = await engine.answer_without_model(
            _conversation(), AssistantParty(customer_id=CUSTOMER), AssistantMessage("what does it cost?"), surface
        )

        assert result.needs_model is True
        engine._intent_service.classify.assert_not_awaited()
        surface._chat.send.assert_not_awaited()

    async def test_a_guardrail_is_answered_in_phase_one_before_any_model(self):
        """D44 — the guardrail on the customer's own words never waits for, or reaches, a model."""
        engine, surface = self._engine(self._welcomed())

        result = await engine.answer_without_model(
            _conversation(), AssistantParty(customer_id=CUSTOMER), AssistantMessage("is this land genuine?"), surface
        )

        assert result.reply.escalation_reason is not None
        engine._intent_service.classify.assert_not_awaited()

    async def test_stop_is_not_an_opt_out_keyword_in_the_portal(self):
        """Meta's STOP vocabulary means nothing here; the word goes to the model like any other."""
        engine, surface = self._engine(self._welcomed())

        result = await engine.answer_without_model(
            _conversation(), AssistantParty(customer_id=CUSTOMER), AssistantMessage("stop"), surface
        )

        assert result.needs_model is True

    async def test_phase_two_classifies_and_answers(self):
        engine, surface = self._engine(self._welcomed(), intent=BotIntent.PRICING)

        result = await engine.answer_with_model(
            _conversation(), AssistantParty(customer_id=CUSTOMER), AssistantMessage("what does it cost?"), surface
        )

        assert "₦5,000" in result.reply.text
        surface._chat.send.assert_awaited_once()

    async def test_an_agent_who_replied_while_the_model_was_thinking_is_not_talked_over(self):
        engine, surface = self._engine(_session_row(mode=BotMode.HUMAN.value))

        result = await engine.answer_with_model(
            _conversation(), AssistantParty(customer_id=CUSTOMER), AssistantMessage("what does it cost?"), surface
        )

        assert result.silent is True
        engine._intent_service.classify.assert_not_awaited()


class TestSessionTurnState:
    def _service(self):
        svc = object.__new__(AssistantSessionService)
        svc._assistant_session_repo = MagicMock(save=MagicMock())
        return svc

    async def test_a_person_joining_cancels_a_turn_waiting_for_the_model(self):
        row = _session_row(pending_turn_message_id=MESSAGE, turn_claimed_at=Utils.datetime_now())
        svc = self._service()
        svc._assistant_session_repo.get_by_conversation = AsyncMock(return_value=row)

        await svc.take_over(_conversation())

        assert row.mode == BotMode.HUMAN.value
        assert row.pending_turn_message_id is None and row.turn_claimed_at is None


def _as_chat_message(value):
    """The web service returns a delivered reply only when it is a real `ChatMessage`."""
    from main.app.domain.communication.chat_message.models import ChatMessage

    message = ChatMessage()
    message.id = value.id
    return message
