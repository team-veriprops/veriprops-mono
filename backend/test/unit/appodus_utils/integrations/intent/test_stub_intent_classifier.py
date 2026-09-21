"""The deterministic keyword classifier (PRD §26.6, D53).

Two properties are being defended. The first is determinism: `ENVIRONMENT=test` pins the
provider here precisely so the guardrail suite cannot flake, and a table that answered
differently on a second run would make every downstream assertion advisory.

The second is the ordering rule. §26.6.4 says a judgment request routes to a human "with
no partial answers", so a message that *also* looks like a pricing or status question must
still read as a judgment request — the table is ordered most-specific-first for that
reason, and the mixed-signal cases below are what hold the order in place.
"""
from __future__ import annotations

import pytest

from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.models import BotIntent
from main.appodus_utils.integrations.intent.stub.stub_intent import StubIntentClassifier


@pytest.fixture
def classifier() -> StubIntentClassifier:
    return StubIntentClassifier()


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Hi Veriprops!", BotIntent.MENU),
        ("hello", BotIntent.MENU),
        ("menu", BotIntent.MENU),
        ("How does it work?", BotIntent.LEARN),
        ("tell me more about veriprops", BotIntent.LEARN),
        ("How much is a verification?", BotIntent.PRICING),
        ("what are your fees", BotIntent.PRICING),
        ("I want to verify a property", BotIntent.START_VERIFICATION),
        ("start a verification please", BotIntent.START_VERIFICATION),
        ("what is the status of my case", BotIntent.CHECK_STATUS),
        ("any update?", BotIntent.CHECK_STATUS),
        ("link my account", BotIntent.LINK_ACCOUNT),
        ("I want to talk to a human", BotIntent.TALK_TO_HUMAN),
        ("can I speak with someone", BotIntent.TALK_TO_HUMAN),
        ("I want a refund", BotIntent.REFUND_OR_CANCELLATION),
        ("please cancel my verification", BotIntent.REFUND_OR_CANCELLATION),
    ],
)
async def test_recognises_each_flow_intent(classifier, message, expected):
    result = await classifier.classify(message)

    assert result.intent == expected
    assert result.provider == IntentProvider.STUB
    assert result.confidence > 0


@pytest.mark.parametrize(
    "message",
    [
        "Is this property legit?",
        "is that land genuine",
        "should i buy this house",
        "what does my trust score mean",
        "can you give me legal advice",
        "do you think the seller is honest",
        "is this a scam",
    ],
)
async def test_judgment_requests_are_recognised_so_they_can_be_refused(classifier, message):
    """§26.1.3/§26.6.4 — the bot never renders a verdict; it recognises the ask and routes it."""
    result = await classifier.classify(message)

    assert result.intent == BotIntent.JUDGMENT_REQUEST


@pytest.mark.parametrize(
    "message",
    [
        # Reads as a pricing question, but the customer is asking about a refund.
        ("how much will my refund be", BotIntent.REFUND_OR_CANCELLATION),
        # Mentions "status" but is asking us to judge a document.
        ("is the status of this title genuine", BotIntent.JUDGMENT_REQUEST),
        # Mentions cost, but the ask is a verdict.
        ("should i buy this land for that cost", BotIntent.JUDGMENT_REQUEST),
        # Names verification, but the question is about money.
        ("how much does it cost to verify a property", BotIntent.PRICING),
        # Names money words nowhere — this one really is intake.
        ("i want to verify a property", BotIntent.START_VERIFICATION),
    ],
    ids=[
        "refund-over-pricing",
        "judgment-over-status",
        "judgment-over-pricing",
        "pricing-over-intake",
        "intake-without-money-words",
    ],
)
async def test_more_specific_intent_wins_when_a_message_carries_two_signals(
    classifier, message
):
    text, expected = message

    result = await classifier.classify(text)

    assert result.intent == expected


@pytest.mark.parametrize(
    "message",
    [
        "",
        "   ",
        "asdkjhaskdjh",
        "Bonjour, je voudrais des informations",  # non-English → never guessed at
        "what is the weather in Lagos",
    ],
)
async def test_unrecognised_messages_are_unknown_at_zero_confidence(classifier, message):
    """An unmatched message must fail the confidence gate outright, not scrape past it."""
    result = await classifier.classify(message)

    assert result.intent == BotIntent.UNKNOWN
    assert result.confidence == 0.0


async def test_classification_is_deterministic(classifier):
    """The whole reason `ENVIRONMENT=test` pins this provider."""
    message = "How much does it cost to verify a property?"

    answers = {(await classifier.classify(message)).intent for _ in range(5)}

    assert answers == {BotIntent.PRICING}
