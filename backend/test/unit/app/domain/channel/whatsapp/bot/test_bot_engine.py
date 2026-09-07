"""The engine's gauntlet, in order (PRD §26.6, WA-11/WA-14/WA-39).

Dispatch order *is* the safety model, so these tests are mostly about **precedence**: what
happens when two rules could both apply. Each case below is a rule beating another rule,
and each of those wins was chosen deliberately:

* a human on the thread beats everything (D57);
* the welcome beats answering, so the disclosure is never buried (§26.6.1);
* guardrails beat the classifier, so no model can talk the bot into a verdict (D44);
* a crash beats nothing — it becomes a warm handover, because a silent bot is
  indistinguishable from a scam that stopped replying (§26.6.5).

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
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentSource
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

class _FakeChannelEventRecorder:
    """Collects the §26.10 facts a turn produced (D80).

    The real recorder swallows its own failures, so a fake that raised would test
    something the production object cannot do.
    """

    def __init__(self):
        self.recorded: list[tuple] = []

    async def record(self, event_type, **kwargs):
        self.recorded.append((event_type, kwargs))

    async def record_payment_if_channel_case(self, verification_id, customer_id):
        self.recorded.append((verification_id, customer_id))

    def types(self):
        return [event_type for event_type, _kwargs in self.recorded]


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
    # §26.10 facts are best-effort side writes (D80). Collected rather than discarded so a
    # test can assert the channel counted what it claims to count.
    recorder = _FakeChannelEventRecorder()
    session_service._channel_events = recorder
    engine._channel_events = recorder
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

    engine._whatsapp_consent_service = MagicMock()
    engine._whatsapp_consent_service.revoke_all = AsyncMock()
    engine._whatsapp_consent_service.grant_utility = AsyncMock()

    # No delegation by default: these cases are about a customer or a stranger, and the
    # delegate branch has its own suite (test_delegate_flow.py).
    engine._case_delegate_service = MagicMock()
    engine._case_delegate_service.resolve_delegate_for_phone = AsyncMock(return_value=None)
    engine._case_delegate_service.revoke_by_phone = AsyncMock(return_value=None)

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
    """§26.6.1 — a bot that greeted *and* answered would bury the disclosure and the
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
    """§26.6.5 — an outage must never look like a scam that stopped replying."""
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
    """§26.4.3 — the bot never reads case data to a number that is not verified."""
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
    """§26.6.2 draws the line at two: guessing a third time is how a bot talks someone out
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
    "kind, reason",
    [
        # A voice note is counted separately: §26.6.3 gives it its own copy ("a team member
        # will listen") and §26.10 asks for voice-note volume by name.
        (InboundKind.AUDIO, EscalationReason.VOICE_NOTE),
        (InboundKind.LOCATION, EscalationReason.UNSUPPORTED_MEDIA),
        (InboundKind.CONTACTS, EscalationReason.UNSUPPORTED_MEDIA),
        (InboundKind.UNSUPPORTED, EscalationReason.UNSUPPORTED_MEDIA),
    ],
    ids=lambda value: getattr(value, "value", value),
)
async def test_media_the_bot_cannot_read_goes_to_a_person(kind, reason):
    """§26.6.3 — a voice note or a dropped pin is acknowledged and handed over, never
    silently ignored."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound("", kind=kind), MagicMock())

    assert reply.escalation_reason == reason


async def test_a_photo_is_answered_with_the_evidence_rule_not_an_apology():
    """§26.6.3/WA-06 — before this flow existed, a customer photographing their survey plan
    got "Sorry, I didn't quite get that": the image kinds were left out of the unreadable
    set on the assumption an upload handoff would catch them, and it had not been built."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN)
    engine._whatsapp_link_service.resolve_user_for_phone = AsyncMock(return_value=None)

    reply = await engine.handle(_inbound("", kind=InboundKind.IMAGE), MagicMock())

    assert reply.is_escalation is False
    assert "verification file" in reply.text


async def test_an_escalation_does_not_silence_the_bot():
    """D57: the thread becomes HUMAN when an agent *replies*, not when the bot asks for
    one — otherwise a customer whose question nobody picked up would get silence."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.TALK_TO_HUMAN)

    await engine.handle(_inbound("I want to talk to a human"), MagicMock())

    assert session.mode == BotMode.BOT.value
    assert session.last_escalation_reason == EscalationReason.EXPLICIT_REQUEST.value


# ── Keyword-only intents: consent and case references (D64, §26.4.3) ──

@pytest.mark.parametrize(
    "word", ["STOP", "stop", "  Stop  ", "unsubscribe", "cancel", "end", "quit"]
)
async def test_stop_revokes_both_consents_in_one_turn(word):
    """D64's full STOP vocabulary. Two things must hold for every one of these words:
    the bot answers *itself* — an opt-out that waits for the next working day is not an
    opt-out — and both §26.4.6 consents go, because the customer said "stop", not "stop
    some"."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN, user_id="cust-1")

    reply = await engine.handle(_inbound(word), MagicMock())

    assert not reply.is_escalation
    assert "didn't quite get that" not in reply.text
    engine._whatsapp_consent_service.revoke_all.assert_awaited_once()
    assert (
        engine._whatsapp_consent_service.revoke_all.await_args.args[1]
        is WhatsAppConsentSource.STOP_KEYWORD
    )


@pytest.mark.parametrize("word", ["START", "unstop", "subscribe"])
async def test_start_restores_utility_only(word):
    """The D64 asymmetry, visible to the customer as well as true in the database: the
    reply has to say marketing stays off, or a one-word message reads as re-consent to
    everything."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN, user_id="cust-1")

    reply = await engine.handle(_inbound(word), MagicMock())

    engine._whatsapp_consent_service.grant_utility.assert_awaited_once()
    engine._whatsapp_consent_service.revoke_all.assert_not_called()
    assert "offers" in reply.text.lower() or "news" in reply.text.lower()


async def test_stop_from_an_unlinked_number_is_still_acknowledged():
    """There is nothing to revoke — we were never messaging them — but "I don't have you
    on file" reads as a refusal to someone who just asked to be left alone."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.UNKNOWN, user_id=None)

    reply = await engine.handle(_inbound("STOP"), MagicMock())

    assert not reply.is_escalation
    engine._whatsapp_consent_service.revoke_all.assert_not_called()
    assert "won't receive" in reply.text


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
    """§26.4.3 outranks recognition: quoting a reference does not prove you own it."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.LEARN, user_id=None)

    reply = await engine.handle(_inbound("status of VP-2026-0001?"), MagicMock())

    assert "isn't linked" in reply.text


# ── Chat intake (§5.1, §26.3.4, D69/D70) ──────────────────────────

def _intake_engine(session, **kwargs):
    engine, sent = _engine(session, **kwargs)
    engine._handoff_token_service = MagicMock()
    engine._handoff_token_service.issue_intake = AsyncMock(return_value="tok-123")
    return engine, sent


async def test_a_stranger_can_start_a_verification_without_an_account():
    """§26.3.4 lists intake as a full WhatsApp capability, and D69 puts identity at the
    landing — so the very first message from an unknown number can begin one."""
    session = _session()
    engine, _sent = _intake_engine(
        session, intent=BotIntent.START_VERIFICATION, user_id=None
    )

    reply = await engine.handle(_inbound("I want to verify a property"), MagicMock())

    assert "what are you verifying" in reply.text.lower()
    assert session.current_flow == BotFlow.INTAKE.value


async def test_the_intake_runs_to_a_handoff_link():
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()

    await engine.handle(_inbound("start a verification"), convo)
    await engine.handle(_inbound("1"), convo)                       # land
    await engine.handle(_inbound("12 Ademola Street"), convo)
    await engine.handle(_inbound("Lagos"), convo)
    reply = await engine.handle(_inbound("2"), convo)               # standard

    assert "/wa/intake/tok-123" in reply.text
    # §26.1.1 — the moment the customer is asked to leave WhatsApp and pay.
    assert "veriprops.ng" in reply.text
    assert session.context["intake"]["property"]["state"] == "Lagos"


async def test_a_re_ask_does_not_count_as_a_failure_to_understand():
    """§26.6.2's two-strikes rule is about the bot being lost, not about a customer
    mistyping inside a form the bot is running — otherwise a fumbled answer escalates a
    conversation that was going fine."""
    session = _session(unmatched_count=1)
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()

    await engine.handle(_inbound("start a verification"), convo)
    reply = await engine.handle(_inbound("no idea"), convo)

    assert not reply.is_escalation
    assert session.unmatched_count == 0


async def test_a_guardrail_still_wins_mid_intake():
    """The gauntlet's order does not relax inside a flow: a verdict request is refused
    even when the bot is halfway through collecting an address."""
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()
    await engine.handle(_inbound("start a verification"), convo)

    reply = await engine.handle(_inbound("is this land genuine?"), convo)

    assert reply.escalation_reason == EscalationReason.GUARDRAIL_TOPIC


async def test_asking_for_the_menu_mid_intake_leaves_the_flow():
    """Dropping the flow hands the turn back to normal classification, which is what
    lets a customer change their mind mid-form instead of being trapped in it."""
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()
    await engine.handle(_inbound("start a verification"), convo)
    # What the real classifier answers for "menu" — the fake above says START_VERIFICATION
    # for everything, which would silently restart the intake it just abandoned.
    engine._intent_service.classify = AsyncMock(
        return_value=IntentResult(
            intent=BotIntent.MENU, confidence=0.9, provider=IntentProvider.STUB
        )
    )

    reply = await engine.handle(_inbound("menu"), convo)

    assert session.current_flow is None
    assert "What would you like to do?" in reply.text


async def test_an_address_containing_a_flow_word_is_still_an_address():
    """The abandon check is deliberately narrow — throwing away a half-finished intake
    because someone's street name contains a keyword is the expensive mistake here."""
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()
    await engine.handle(_inbound("start a verification"), convo)
    await engine.handle(_inbound("1"), convo)

    await engine.handle(_inbound("12 Menu Close, Lekki"), convo)

    assert session.current_flow == BotFlow.INTAKE.value
    assert session.context["intake"]["property"]["address"] == "12 Menu Close, Lekki"


# ── Short-code continuation (§26.4.3, D58) ────────────────────────

async def test_a_quoted_reference_picks_that_case_up():
    session = _session()
    engine, _sent = _engine(
        session,
        intent=BotIntent.LEARN,
        user_id=USER_ID,
        cases=[
            _FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS),
            _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAID),
        ],
    )

    reply = await engine.handle(_inbound("continue VP-2026-0002"), MagicMock())

    assert "VP-2026-0002" in reply.text
    assert "VP-2026-0001" not in reply.text


async def test_a_reference_that_is_not_yours_reads_as_not_found():
    """Case references travel on receipts and reports. Answering "that isn't yours" would
    confirm the case exists and make the reference space probeable from any number."""
    session = _session()
    engine, _sent = _engine(
        session,
        intent=BotIntent.LEARN,
        user_id=USER_ID,
        cases=[_FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS)],
    )

    reply = await engine.handle(_inbound("continue VP-2026-9999"), MagicMock())

    assert "can't find that reference" in reply.text
    assert "not yours" not in reply.text.lower()


async def test_continuation_refuses_an_unlinked_number():
    """§26.4.3 again — quoting a reference is not proof of owning it."""
    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.LEARN, user_id=None)

    reply = await engine.handle(_inbound("continue VP-2026-0001"), MagicMock())

    assert "isn't linked" in reply.text
    assert "VP-2026-0001" not in reply.text


async def test_a_thirty_day_gap_drops_a_half_finished_intake():
    """§26.6.1's welcome is also a reset. Resuming a month-old intake would answer a
    question about a property the customer has almost certainly moved on from, and would
    show a stale flow beside the thread in the console."""
    session = _session(
        welcomed_at=Utils.datetime_now() - timedelta(days=31),
        current_flow=BotFlow.INTAKE.value,
        step=2,
        context={"intake": {"property": {"address": "old answer"}}},
    )
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)

    reply = await engine.handle(_inbound("hello again"), MagicMock())

    assert "automated assistant" in reply.text
    assert session.current_flow is None
    assert session.context is None


async def test_a_finished_intake_does_not_re_send_a_link_on_the_next_message():
    """The bug this guards: a completed intake left parked at DONE reads whatever the
    customer says next — "thanks", "how long does it take" — as another answer, and sends
    a second link every time."""
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.START_VERIFICATION)
    convo = MagicMock()
    for answer in ("start a verification", "1", "12 Ademola Street", "Lagos", "2"):
        await engine.handle(_inbound(answer), convo)
    assert session.current_flow is None

    engine._intent_service.classify = AsyncMock(
        return_value=IntentResult(
            intent=BotIntent.LEARN, confidence=0.9, provider=IntentProvider.STUB
        )
    )
    reply = await engine.handle(_inbound("thanks, how long does it take?"), convo)

    assert "/wa/intake/" not in reply.text


@pytest.mark.parametrize("phrase", ["pay", "new link", "resend", "expired", "  Link  "])
async def test_a_customer_can_ask_for_a_fresh_link(phrase):
    """A 15-minute link expires easily, and §26.10 makes intake→payment the headline
    number — re-asking four questions is the cheapest conversion to lose."""
    session = _session(context={"intake": {"property": {"address": "12 Ademola Street"}}})
    engine, _sent = _intake_engine(session, intent=BotIntent.UNKNOWN)

    reply = await engine.handle(_inbound(phrase), MagicMock())

    assert "/wa/intake/tok-123" in reply.text
    assert "veriprops.ng" in reply.text


async def test_asking_for_a_link_with_no_intake_behind_it_classifies_normally():
    """Otherwise "pay" from someone who never ran an intake gets a link to nothing."""
    session = _session()
    engine, _sent = _intake_engine(session, intent=BotIntent.PRICING)

    reply = await engine.handle(_inbound("pay"), MagicMock())

    assert "/wa/intake/" not in reply.text
    assert "₦5,000" in reply.text


# ── Pay and report handoffs (§26.3.4, §26.4.2, WA-17) ──────────────
#
# §26.3.4 marks three actions HANDOFF. Only `upload` had a producer, so "how do I pay?"
# and "send me my report" both fell through to "I didn't quite get that" — and the
# `/wa/pay/<token>` and `/wa/report/<token>` landings, both fully built, were unreachable
# from a real conversation.

def _handoff_engine(session, **kwargs):
    engine, sent = _engine(session, **kwargs)
    engine._handoff_token_service = MagicMock()
    engine._handoff_token_service.issue = AsyncMock(return_value="tok-abc")
    engine._handoff_token_service.issue_intake = AsyncMock(return_value="tok-123")
    engine._verification_repo.get_by_vid = AsyncMock(
        side_effect=lambda vid: next(
            (row for row in kwargs.get("cases", ()) if row.vid == vid), None
        )
    )
    return engine, sent


async def test_asking_to_pay_hands_over_a_pay_link_for_the_unpaid_case():
    session = _session()
    case = _FakeVerificationRow("VP-2026-0001", VerificationStatus.PAYMENT_PENDING)
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.PAY, user_id=USER_ID, cases=[case]
    )

    reply = await engine.handle(_inbound("how do I pay?"), MagicMock())

    assert "/wa/pay/tok-abc" in reply.text
    # §26.1.1 — the pledge rides every payment handoff. This is the message an
    # impersonator would imitate, so it is the one that most needs it.
    assert "veriprops.ng" in reply.text
    assert session.current_flow is None


async def test_asking_for_a_report_hands_over_a_report_link():
    session = _session()
    case = _FakeVerificationRow("VP-2026-0001", VerificationStatus.COMPLETED)
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.VIEW_REPORT, user_id=USER_ID, cases=[case]
    )

    reply = await engine.handle(_inbound("send me my report"), MagicMock())

    assert "/wa/report/tok-abc" in reply.text


async def test_the_pay_link_is_never_issued_to_an_unlinked_number():
    """§26.4.3 — a pay token names a customer and a case, so issuing one from a phone
    number alone would mean guessing whose money is being asked for."""
    session = _session()
    engine, _sent = _handoff_engine(session, intent=BotIntent.PAY, user_id=None)

    reply = await engine.handle(_inbound("I want to pay"), MagicMock())

    assert "/wa/pay/" not in reply.text
    assert "link my account" in reply.text


async def test_a_customer_with_nothing_to_pay_for_is_told_so_without_a_link():
    session = _session()
    case = _FakeVerificationRow("VP-2026-0001", VerificationStatus.IN_PROGRESS)
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.PAY, user_id=USER_ID, cases=[case]
    )

    reply = await engine.handle(_inbound("I want to pay"), MagicMock())

    assert "/wa/pay/" not in reply.text
    assert "waiting for payment" in reply.text


async def test_two_unpaid_cases_are_asked_about_then_resolved_to_one_link():
    """The same numbered question the status and document flows ask, answered the same
    way — and the link is minted only once the bot knows which case it is for."""
    session = _session()
    cases = [
        _FakeVerificationRow("VP-2026-0001", VerificationStatus.PAYMENT_PENDING),
        _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAYMENT_PENDING, "prop-2"),
    ]
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.PAY, user_id=USER_ID, cases=cases
    )
    convo = MagicMock()

    asked = await engine.handle(_inbound("how do I pay"), convo)
    assert "/wa/pay/" not in asked.text
    assert session.current_flow == BotFlow.PAY.value

    chosen = await engine.handle(_inbound("2"), convo)
    assert "/wa/pay/tok-abc" in chosen.text
    assert session.current_flow is None


async def test_changing_the_subject_mid_choice_classifies_fresh_rather_than_nagging():
    session = _session()
    cases = [
        _FakeVerificationRow("VP-2026-0001", VerificationStatus.PAYMENT_PENDING),
        _FakeVerificationRow("VP-2026-0002", VerificationStatus.PAYMENT_PENDING, "prop-2"),
    ]
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.PAY, user_id=USER_ID, cases=cases
    )
    convo = MagicMock()
    await engine.handle(_inbound("how do I pay"), convo)

    engine._intent_service.classify = AsyncMock(
        return_value=IntentResult(
            intent=BotIntent.PRICING, confidence=0.9, provider=IntentProvider.STUB
        )
    )
    reply = await engine.handle(_inbound("actually, what does it cost?"), convo)

    assert "₦5,000" in reply.text
    assert session.current_flow is None


async def test_a_report_request_does_not_hand_over_a_payment_link():
    """The two links authorize different actions, so answering one with the other would
    send a customer to pay when they asked to read."""
    session = _session()
    case = _FakeVerificationRow("VP-2026-0001", VerificationStatus.PAYMENT_PENDING)
    engine, _sent = _handoff_engine(
        session, intent=BotIntent.VIEW_REPORT, user_id=USER_ID, cases=[case]
    )

    reply = await engine.handle(_inbound("send me my report"), MagicMock())

    assert "/wa/pay/" not in reply.text
    assert "/wa/report/" not in reply.text


async def test_a_retained_intake_still_wins_over_the_pay_intent():
    """Precedence: someone mid-intake who types "pay" wants the link to the answers they
    just gave, not a link to a case they have not created yet."""
    session = _session(context={"intake": {"property": {"address": "12 Ademola Street"}}})
    engine, _sent = _handoff_engine(session, intent=BotIntent.PAY, user_id=USER_ID)

    reply = await engine.handle(_inbound("pay"), MagicMock())

    assert "/wa/intake/tok-123" in reply.text


# ── The §26.6.5 failure drill (§26.11 launch gate, WA-40) ──────────

async def test_an_armed_fault_becomes_a_warm_handover_like_any_other_crash():
    """The drill has to take the real path, not a special one — otherwise it proves the
    drill works rather than that the fallback does."""
    from main.app.core import fault_injection
    from main.app.core.fault_injection import FaultPoint

    session = _session()
    engine, sent = _engine(session, intent=BotIntent.PRICING)
    fault_injection.arm(FaultPoint.WHATSAPP_BOT_TURN)
    try:
        reply = await engine.handle(_inbound("how much?"), MagicMock())
    finally:
        fault_injection.disarm_all()

    assert reply.escalation_reason == EscalationReason.PIPELINE_FAILURE
    # A bot that goes quiet is indistinguishable from a scam that stopped replying.
    assert sent and "technical" in sent[0].lower()


async def test_a_fault_is_one_shot_so_a_forgotten_arm_cannot_silence_a_number():
    from main.app.core import fault_injection
    from main.app.core.fault_injection import FaultPoint

    session = _session()
    engine, _sent = _engine(session, intent=BotIntent.PRICING)
    fault_injection.arm(FaultPoint.WHATSAPP_BOT_TURN)
    try:
        await engine.handle(_inbound("how much?"), MagicMock())
        recovered = await engine.handle(_inbound("how much?"), MagicMock())
    finally:
        fault_injection.disarm_all()

    assert recovered.escalation_reason is None
    assert "₦5,000" in recovered.text
