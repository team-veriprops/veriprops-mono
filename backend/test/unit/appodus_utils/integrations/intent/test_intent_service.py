"""The confidence gate and the never-raises contract (PRD §7.6.4, D53).

`IntentService` is the only place a classifier's answer becomes something the bot will act
on, so it is the only place these two rules need to hold — and the only place a regression
in them would be silent. A gate that let a 0.2-confidence guess through would have the bot
answering a question it did not understand, which is the exact failure §7.6.4 names.
"""
from __future__ import annotations

import pytest

from main.app.config.settings import settings
from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.interface import IIntentClassifier
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult
from main.appodus_utils.integrations.intent.service import IntentService


class _FakeClassifier(IIntentClassifier):
    """Answers whatever the test hands it — including things a live model might."""

    def __init__(self, result: IntentResult):
        self._result = result

    @property
    def platform(self) -> IntentProvider:
        return IntentProvider.STUB

    async def classify(self, text: str) -> IntentResult:
        return self._result


class _FakeFactory:
    def __init__(self, classifier: IIntentClassifier):
        self._classifier = classifier

    def get_active_classifier(self) -> IIntentClassifier:
        return self._classifier


def _service_answering(result: IntentResult) -> IntentService:
    return IntentService(_FakeFactory(_FakeClassifier(result)))


async def test_confident_answer_passes_through():
    service = _service_answering(
        IntentResult(intent=BotIntent.PRICING, confidence=0.95, provider=IntentProvider.STUB)
    )

    assert (await service.classify("how much?")).intent == BotIntent.PRICING


async def test_low_confidence_answer_becomes_unknown():
    """§7.6.4 — low confidence routes to a human; it is never acted on as a guess."""
    below_gate = max(0.0, settings.INTENT_MIN_CONFIDENCE - 0.1)
    service = _service_answering(
        IntentResult(intent=BotIntent.PRICING, confidence=below_gate, provider=IntentProvider.STUB)
    )

    result = await service.classify("something ambiguous")

    assert result.intent == BotIntent.UNKNOWN
    # The provider survives the downgrade so §7.10 can tell an unsure model from an
    # uncovered topic when the escalation rate is read.
    assert result.provider == IntentProvider.STUB


async def test_answer_exactly_at_the_gate_is_accepted():
    service = _service_answering(
        IntentResult(
            intent=BotIntent.CHECK_STATUS,
            confidence=settings.INTENT_MIN_CONFIDENCE,
            provider=IntentProvider.STUB,
        )
    )

    assert (await service.classify("any news")).intent == BotIntent.CHECK_STATUS


async def test_unknown_is_returned_unchanged_regardless_of_confidence():
    """A classifier that reports UNKNOWN with high confidence still means 'route to a human'."""
    service = _service_answering(
        IntentResult(intent=BotIntent.UNKNOWN, confidence=1.0, provider=IntentProvider.STUB)
    )

    assert (await service.classify("???")).intent == BotIntent.UNKNOWN


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("PRICING", BotIntent.PRICING),
        ("pricing", BotIntent.PRICING),
        ("  CHECK_STATUS  ", BotIntent.CHECK_STATUS),
        # Off-vocabulary answers a model can still produce.
        ("BOOK_A_FLIGHT", BotIntent.UNKNOWN),
        ("", BotIntent.UNKNOWN),
        (None, BotIntent.UNKNOWN),
        (42, BotIntent.UNKNOWN),
        # In the enum, but reserved for keyword matching — a model may not revoke
        # someone's consent or claim a case by inference.
        ("STOP_MESSAGES", BotIntent.UNKNOWN),
        ("CONTINUE_CASE", BotIntent.UNKNOWN),
    ],
)
def test_coerce_intent_closes_the_vocabulary(raw, expected):
    from main.appodus_utils.integrations.intent.models import coerce_intent

    assert coerce_intent(raw) == expected
