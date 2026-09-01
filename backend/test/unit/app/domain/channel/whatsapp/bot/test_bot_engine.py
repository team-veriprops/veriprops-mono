"""The engine's gauntlet, in order (PRD §7.6, WA-11/WA-14/WA-39).

Dispatch order *is* the safety model, so these tests are mostly about **precedence**: what
happens when two rules could both apply. Each case below is a rule beating another rule,
and each of those wins was chosen deliberately:

* a human on the thread beats everything (D57);
* the welcome beats answering, so the disclosure is never buried (§7.6.1);
* guardrails beat the classifier, so no model can talk the bot into a verdict (D44);
* a crash beats nothing — it becomes a warm handover, because a silent bot is
  indistinguishable from a scam that stopped replying (§7.6.5).

The collaborators are fakes rather than mocks with assertions on calls: what matters is
the words the customer reads and the state the session lands in, not which method ran.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.channel.whatsapp.bot.engine import WhatsAppBotEngine
from main.app.domain.channel.whatsapp.bot.session.models import (
    BotFlow,
    BotMode,
    EscalationReason,
    WhatsAppBotSession,
)
from main.app.domain.channel.whatsapp.bot.session.service import WhatsAppBotSessionService
from main.app.domain.channel.whatsapp.bot.support_hours import Coverage, CoverageState
from main.app.domain.verification.pricing_config.models import (
    PricingTierDto,
    TierPricingViewDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult
from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    InboundWhatsAppMessage,
)

PHONE = "+2348012345678"
USER_ID = "11111111-1111-1111-1111-111111111111"


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


# ─── Fakes ────────────────────────────────────────────────────────

class _FakeSessionRepo:
    """Just enough of the repo for the real session service to run against memory."""

    def __init__(self, session: WhatsAppBotSession):
        self.session = session

    async def get_by_phone(self, phone_e164):
        return self.session

    def save(self, session):
        return session


def _session(**overrides) -> WhatsAppBotSession:
    """A session that has already been welcomed, unless a test says otherwise.

    The welcome short-circuits every turn by design, so "already welcomed" is the state
    almost every test needs — and making it the default keeps each test about the one
    rule it is checking.
    """
    session = WhatsAppBotSession()
    session.phone_e164 = PHONE
    session.mode = BotMode.BOT.value
    session.step = 0
    session.unmatched_count = 0
    session.welcomed_at = Utils.datetime_now() - timedelta(days=1)
    session.last_inbound_at = session.welcomed_at
    session.context = None
    session.current_flow = None
    for field, value in overrides.items():
        setattr(session, field, value)
    return session


class _FakeVerificationRow:
    def __init__(self, vid, status, property_id="prop-1"):
        self.id = Utils.generate_uuid()
        self.vid = vid
        self.status = status.value
        self.property_id = property_id
        self.sla_due_date = date(2026, 9, 15)


def _engine(
    session: WhatsAppBotSession,
    *,
    intent: BotIntent = BotIntent.UNKNOWN,
    user_id=None,
    cases=(),
    coverage=Coverage(CoverageState.OPEN, 12),
) -> tuple[WhatsAppBotEngine, list[str]]:
    """An engine wired to fakes, plus the list of replies it sent."""
    sent: list[str] = []

    engine = object.__new__(WhatsAppBotEngine)

    session_service = object.__new__(WhatsAppBotSessionService)
    session_service._whatsapp_bot_session_repo = _FakeSessionRepo(session)
    engine._whatsapp_bot_session_service = session_service

    sender = MagicMock()

    async def _reply(conversation, phone, text):
        sent.append(text)

    sender.reply = _reply
    engine._whatsapp_bot_sender = sender

    engine._whatsapp_link_service = MagicMock()
    engine._whatsapp_link_service.resolve_user_for_phone = AsyncMock(return_value=user_id)

    engine._intent_service = MagicMock()
    engine._intent_service.classify = AsyncMock(
        return_value=IntentResult(intent=intent, confidence=0.9, provider=IntentProvider.STUB)
    )

    engine._support_hours_service = MagicMock()
    engine._support_hours_service.coverage = AsyncMock(return_value=coverage)

    engine._pricing_config_service = MagicMock()
    engine._pricing_config_service.view = AsyncMock(
        return_value=TierPricingViewDto(
            tiers=[PricingTierDto(tier=VerificationTier.BASIC, price_ngn_minor=5_000_00)]
        )
    )

    engine._verification_repo = MagicMock()
    engine._verification_repo.page_for_customer = AsyncMock(
        return_value=(list(cases), len(cases))
    )

    engine._verification_task_repo = MagicMock()
    engine._verification_task_repo.get_by_role = AsyncMock(return_value=None)

    engine._property_service = MagicMock()
    prop = MagicMock()
    prop.address = "12 Ademola Street"
    prop.landmark = None
    prop.lga = "Ikeja"
    prop.state = "Lagos"
    engine._property_service.get_model = AsyncMock(return_value=prop)

    engine._user_repo = MagicMock()
    engine._user_repo.list_admins = AsyncMock(return_value=[])

    return engine, sent


def _inbound(text: str, kind: InboundKind = InboundKind.TEXT) -> InboundWhatsAppMessage:
    return InboundWhatsAppMessage(
        wamid=f"wamid.{Utils.generate_uuid()}",
        from_phone=PHONE,
        kind=kind,
        text=text,
        received_at=Utils.datetime_now(),
        raw={},
    )


# ─── Precedence ───────────────────────────────────────────────────

async def test_the_bot_stays_silent_while_a_human_owns_the_thread():
    """D57 — talking over an agent mid-conversation is the failure customers notice most."""
    session = _session(mode=BotMode.HUMAN.value)
    engine, sent = _engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("how much?"), MagicMock())

    assert reply is None
    assert sent == []


async def test_first_contact_gets_the_welcome_and_nothing_else():
    """§7.6.1 — a bot that greeted *and* answered would bury the disclosure and the
    payment pledge under a wall of text."""
    session = _session(welcomed_at=None, last_inbound_at=None)
    engine, sent = _engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("how much is it"), MagicMock())

    assert "automated assistant" in reply.text
    assert "veriprops.ng" in reply.text
    assert "₦" not in reply.text
    assert len(sent) == 1


async def test_a_returning_customer_is_welcomed_again_after_thirty_days():
    session = _session(welcomed_at=Utils.datetime_now() - timedelta(days=31))
    engine, _sent = _engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("hello again"), MagicMock())

    assert "automated assistant" in reply.text


async def test_a_recent_customer_is_not_re_welcomed():
    session = _session(welcomed_at=Utils.datetime_now() - timedelta(days=29))
    engine, _sent = _engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("how much is it"), MagicMock())

    assert "automated assistant" not in reply.text
    assert "₦5,000" in reply.text


async def test_a_guardrail_beats_the_classifier():
    """D44 — the classifier is told the message is about pricing, and it does not matter.
    The guardrail check never consults it."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("is this land genuine? and how much?"), MagicMock())

    assert reply.escalation_reason == EscalationReason.GUARDRAIL_TOPIC
    assert "₦" not in reply.text


async def test_an_intent_guardrail_catches_what_phrasing_did_not():
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.JUDGMENT_REQUEST)

    reply = await engine.handle(
        _inbound("what's your view on the survey plan I sent"), MagicMock()
    )

    assert reply.escalation_reason == EscalationReason.GUARDRAIL_TOPIC


async def test_a_crash_becomes_a_warm_handover():
    """§7.6.5 — an outage must never look like a scam that stopped replying."""
    session = _session()
    engine, sent = _engine(session, intent=BotIntent.PRICING)
    engine._pricing_config_service.view = AsyncMock(side_effect=RuntimeError("provider down"))

    reply = await engine.handle(_inbound("what are your prices"), MagicMock())

    assert reply.escalation_reason == EscalationReason.PIPELINE_FAILURE
    assert "technical issue" in reply.text
    assert len(sent) == 1


# ─── Menu and answers ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "choice, expected_fragment",
    [("1", "Here's how Verify works"), ("5", "₦5,000")],
)
async def test_menu_numbers_are_deterministic(choice, expected_fragment):
    """The welcome invites numbers, so the numbers must work — and must keep working
    through a classifier outage, which is why they are matched before it."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound(choice), MagicMock())

    assert expected_fragment in reply.text


async def test_menu_number_four_asks_for_a_person():
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound("4"), MagicMock())

    assert reply.escalation_reason == EscalationReason.EXPLICIT_REQUEST


async def test_an_faq_question_is_answered_from_the_content_set():
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.LEARN)

    reply = await engine.handle(_inbound("is my data safe?"), MagicMock())

    assert "behind your own" in reply.text


# ─── Status ───────────────────────────────────────────────────────

async def test_status_refuses_an_unlinked_number():
    """§7.4.3 — the bot never reads case data to a number that is not verified."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.CHECK_STATUS, user_id=None)

    reply = await engine.handle(_inbound("what's my status"), MagicMock())

    assert "isn't linked" in reply.text
    assert "VP-" not in reply.text


async def test_status_answers_a_linked_number_with_its_one_case():
    session = _session()
    engine, _sent = _engine(
        session,
        intent=BotIntent.CHECK_STATUS,
        user_id=USER_ID,
        cases=[_FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS)],
    )

    reply = await engine.handle(_inbound("any update"), MagicMock())

    assert "VP-2026-0001" in reply.text
    assert "12 Ademola Street, Ikeja, Lagos" in reply.text


async def test_status_with_several_cases_parks_the_flow_and_asks():
    session = _session()
    engine, _sent = _engine(
        session,
        intent=BotIntent.CHECK_STATUS,
        user_id=USER_ID,
        cases=[
            _FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS),
            _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAID),
        ],
    )

    reply = await engine.handle(_inbound("any update"), MagicMock())

    assert "Which one" in reply.text
    assert session.current_flow == BotFlow.STATUS.value
    assert session.context["vids"] == ["VP-2026-0001", "VP-2026-0002"]


async def test_the_parked_flow_answers_the_next_message():
    session = _session(
        current_flow=BotFlow.STATUS.value, context={"vids": ["VP-2026-0001", "VP-2026-0002"]}
    )
    engine, _sent = _engine(
        session,
        intent=BotIntent.UNKNOWN,
        user_id=USER_ID,
        cases=[
            _FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS),
            _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAID),
        ],
    )

    reply = await engine.handle(_inbound("2"), MagicMock())

    assert "VP-2026-0002" in reply.text
    assert session.current_flow is None


async def test_changing_the_subject_mid_flow_is_not_treated_as_a_choice():
    """A flow that insisted on an answer would trap a customer who changed their mind."""
    session = _session(
        current_flow=BotFlow.STATUS.value, context={"vids": ["VP-2026-0001", "VP-2026-0002"]}
    )
    engine, _sent = _engine(
        session,
        intent=BotIntent.PRICING,
        user_id=USER_ID,
        cases=[
            _FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS),
            _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAID),
        ],
    )

    reply = await engine.handle(_inbound("actually, what does it cost?"), MagicMock())

    assert "₦5,000" in reply.text
    assert session.current_flow is None


async def test_a_link_revoked_mid_flow_re_runs_the_identity_check():
    """The offer was made to a linked number; if that stopped being true between the
    question and the answer, the case list must not be served from the stale offer."""
    session = _session(
        current_flow=BotFlow.STATUS.value, context={"vids": ["VP-2026-0001"]}
    )
    engine, _sent = _engine(session, intent=BotIntent.CHECK_STATUS, user_id=None)

    reply = await engine.handle(_inbound("any update on that one"), MagicMock())

    assert "isn't linked" in reply.text
    assert session.current_flow is None


# ─── Unmatched and escalation ─────────────────────────────────────

async def test_the_first_miss_re_offers_the_menu():
    """Usually all a confused customer needs."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound("qwertyuiop"), MagicMock())

    assert not reply.is_escalation
    assert "didn't quite get that" in reply.text
    assert session.unmatched_count == 1


async def test_the_second_consecutive_miss_escalates():
    """§7.6.2 draws the line at two: guessing a third time is how a bot talks someone out
    of the product."""
    session = _session(unmatched_count=1)
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound("asdfgh"), MagicMock())

    assert reply.escalation_reason == EscalationReason.UNMATCHED_INTENTS
    assert session.last_escalation_reason == EscalationReason.UNMATCHED_INTENTS.value


async def test_a_understood_turn_resets_the_miss_counter():
    """The rule is *consecutive* misses — a customer who once mistyped must not be
    escalated forever after."""
    session = _session(unmatched_count=1)
    engine, _sent = _engine(session, intent=BotIntent.PRICING)

    await engine.handle(_inbound("what are your prices"), MagicMock())

    assert session.unmatched_count == 0


@pytest.mark.parametrize(
    "kind",
    [InboundKind.AUDIO, InboundKind.LOCATION, InboundKind.CONTACTS, InboundKind.UNSUPPORTED],
    ids=lambda k: k.value,
)
async def test_media_the_bot_cannot_read_goes_to_a_person(kind):
    """§7.6.3 — a voice note or a dropped pin is acknowledged and handed over, never
    silently ignored."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound("", kind=kind), MagicMock())

    assert reply.escalation_reason == EscalationReason.UNSUPPORTED_MEDIA


async def test_an_escalation_does_not_silence_the_bot():
    """D57: the thread becomes HUMAN when an agent *replies*, not when the bot asks for
    one — otherwise a customer whose question nobody picked up would get silence."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.TALK_TO_HUMAN)

    await engine.handle(_inbound("I want to talk to a human"), MagicMock())

    assert session.mode == BotMode.BOT.value
    assert session.last_escalation_reason == EscalationReason.EXPLICIT_REQUEST.value


# ── Keyword-only intents: consent and case references (D64, §7.4.3) ──

@pytest.mark.parametrize(
    "word", ["STOP", "stop", "  Stop  ", "unsubscribe", "cancel messages"]
)
async def test_stop_is_never_answered_with_i_did_not_understand(word):
    """Meta and the customer both treat STOP as binding. Until S8's consent ledger lands,
    a person honours it — but the one thing the bot must never do is reply "sorry, I
    didn't quite get that" to an opt-out."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound(word), MagicMock())

    assert reply.is_escalation
    assert "didn't quite get that" not in reply.text


@pytest.mark.parametrize("word", ["START", "resume"])
async def test_start_is_recognised_too(word):
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound(word), MagicMock())

    assert reply.is_escalation


async def test_a_consent_keyword_never_reaches_the_classifier():
    """D64 — a model must not be able to revoke someone's consent by inference, so the
    keyword is matched on the customer's literal word before classification runs."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.PRICING)

    await engine.handle(_inbound("STOP"), MagicMock())

    engine._intent_service.classify.assert_not_awaited()


async def test_a_quoted_case_reference_outranks_the_classifier():
    """The customer quoting `VP-2026-0001` is a literal fact about the message, not an
    inference — so it wins over whatever the classifier makes of the surrounding words."""
    session = _session()
    engine, _sent = _engine(
        session,
        intent=BotIntent.LEARN,
        user_id=USER_ID,
        cases=[_FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS)],
    )

    reply = await engine.handle(
        _inbound("any news on VP-2026-0001 please"), MagicMock()
    )

    assert "VP-2026-0001" in reply.text


async def test_a_case_reference_still_respects_the_identity_gate():
    """§7.4.3 outranks recognition: quoting a reference does not prove you own it."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.LEARN, user_id=None)

    reply = await engine.handle(_inbound("status of VP-2026-0001?"), MagicMock())

    assert "isn't linked" in reply.text
