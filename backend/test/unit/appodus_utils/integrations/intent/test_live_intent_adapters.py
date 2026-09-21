"""The live adapters' failure behaviour (PRD §26.6.4/§26.6.5, D53).

These tests never call a model — `ENVIRONMENT=test` forbids it, and that is the point.
What they pin down is what happens when the model is *unreachable or wrong*, because
that is the path a customer actually feels: a classifier that raised would take the bot
down and §26.6.5 says an outage must never look like a scam that stopped replying.

Every branch below has the same expected outcome — `UNKNOWN`, which routes to a human.
The value is in proving there is no branch that escapes as an exception.
"""
from __future__ import annotations

import pytest

from main.app.config.settings import settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER, IntentProvider
from main.appodus_utils.integrations.intent.claude.claude_intent import ClaudeIntentClassifier
from main.appodus_utils.integrations.intent.models import BotIntent
from main.appodus_utils.integrations.intent.openai_compatible.openai_compatible_intent import (
    OpenAiCompatibleIntentClassifier,
    _parse_answer,
    _read_confidence,
)


class _ToolUseBlock:
    """The shape the SDK returns for a forced tool call."""

    type = "tool_use"

    def __init__(self, name: str, payload):
        self.name = name
        self.input = payload


class _Response:
    def __init__(self, content):
        self.content = content


# ── Claude adapter ────────────────────────────────────────────────

async def test_claude_without_a_key_routes_to_a_human(monkeypatch):
    """An unconfigured live provider degrades; it does not raise on the inbound path."""
    monkeypatch.setattr(settings, "INTENT_API_KEY", SECRET_PLACEHOLDER, raising=False)

    result = await ClaudeIntentClassifier().classify("how much does it cost")

    assert result.intent == BotIntent.UNKNOWN
    assert result.provider == IntentProvider.ANTHROPIC


def test_claude_reads_a_forced_tool_call():
    classifier = ClaudeIntentClassifier()

    result = classifier._read(
        _Response([_ToolUseBlock("classify_intent", {"intent": "PRICING", "confidence": 0.91})])
    )

    assert result.intent == BotIntent.PRICING
    assert result.confidence == pytest.approx(0.91)


@pytest.mark.parametrize(
    "content",
    [
        [],                                                     # no blocks at all
        [_ToolUseBlock("something_else", {"intent": "PRICING", "confidence": 1})],
        [_ToolUseBlock("classify_intent", {"intent": "BOOK_A_FLIGHT", "confidence": 1})],
        [_ToolUseBlock("classify_intent", "not a dict")],
        [_ToolUseBlock("classify_intent", {})],
    ],
    ids=["empty", "wrong-tool", "off-vocabulary", "non-dict-input", "missing-fields"],
)
def test_claude_unreadable_answers_become_unknown(content):
    assert ClaudeIntentClassifier()._read(_Response(content)).intent == BotIntent.UNKNOWN


# ── OpenAI-compatible adapter ─────────────────────────────────────

@pytest.mark.parametrize(
    "base_url, api_key",
    [("", "sk-real-key"), ("https://api.example.com/v1", SECRET_PLACEHOLDER), ("", "")],
    ids=["no-base-url", "placeholder-key", "neither"],
)
async def test_openai_compatible_without_config_routes_to_a_human(monkeypatch, base_url, api_key):
    monkeypatch.setattr(settings, "INTENT_API_BASE_URL", base_url, raising=False)
    monkeypatch.setattr(settings, "INTENT_API_KEY", api_key, raising=False)

    result = await OpenAiCompatibleIntentClassifier().classify("how much does it cost")

    assert result.intent == BotIntent.UNKNOWN
    assert result.provider == IntentProvider.OPENAI_COMPATIBLE


def test_openai_compatible_reads_a_json_answer():
    body = {
        "choices": [{"message": {"content": '{"intent": "CHECK_STATUS", "confidence": 0.8}'}}]
    }

    result = OpenAiCompatibleIntentClassifier()._read(body)

    assert result.intent == BotIntent.CHECK_STATUS
    assert result.confidence == pytest.approx(0.8)


@pytest.mark.parametrize(
    "content, expected",
    [
        # Providers that ignore a response-format request still answer usefully; the
        # parse is written to survive their prose and fences rather than reject them.
        ('```json\n{"intent": "PRICING", "confidence": 0.7}\n```', BotIntent.PRICING),
        ('Sure! {"intent": "LEARN", "confidence": 0.9}', BotIntent.LEARN),
        ("PRICING", BotIntent.UNKNOWN),          # bare label, not the agreed shape
        ("{not json}", BotIntent.UNKNOWN),
        ("", BotIntent.UNKNOWN),
        ('{"intent": "BOOK_A_FLIGHT", "confidence": 1}', BotIntent.UNKNOWN),
        ('["PRICING"]', BotIntent.UNKNOWN),      # JSON, but not an object
    ],
    ids=["fenced", "prefaced", "bare-label", "malformed", "empty", "off-vocabulary", "not-object"],
)
def test_openai_compatible_tolerates_shape_drift_but_never_guesses(content, expected):
    body = {"choices": [{"message": {"content": content}}]}

    assert OpenAiCompatibleIntentClassifier()._read(body).intent == expected


@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}, None],
    ids=["empty", "no-choices", "no-message", "no-content", "null"],
)
def test_openai_compatible_malformed_envelope_becomes_unknown(body):
    assert OpenAiCompatibleIntentClassifier()._read(body).intent == BotIntent.UNKNOWN


def test_json_object_is_extracted_from_surrounding_text():
    assert _parse_answer('noise {"a": 1} trailing') == {"a": 1}
    assert _parse_answer("no object here") is None


@pytest.mark.parametrize(
    "raw, expected",
    [(0.5, 0.5), ("0.7", 0.7), (2, 1.0), (-1, 0.0), (None, 0.0), ("high", 0.0), ({}, 0.0)],
)
def test_confidence_is_clamped_and_an_unreadable_score_reads_as_zero(raw, expected):
    """Zero fails the gate, which routes to a human — the right answer for output we
    could not parse."""
    assert _read_confidence(raw) == pytest.approx(expected)
