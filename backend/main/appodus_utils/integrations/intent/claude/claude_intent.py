"""Anthropic intent classifier — the live default (D53).

Classification is forced through a **tool call** rather than free text: the tool's schema
declares `intent` as an enum, which is the most reliable way to get an answer from the
closed set §26.6.4 depends on. The answer is still run through ``coerce_intent`` on the way
out — a schema is a strong constraint, not a proof, and the cost of trusting it wrongly is
the bot acting on an intent nobody defined.

Model choice is a setting (``INTENT_MODEL``, Haiku-class by default): this is one
short closed-set classification per inbound message, the cheapest and fastest tier that
does it well, and a provider or model change stays a config change (D48).
"""
from __future__ import annotations

from typing import Any, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER, IntentProvider
from main.appodus_utils.integrations.intent.interface import IIntentClassifier
from main.appodus_utils.integrations.intent.models import (
    CLASSIFIABLE_INTENTS,
    BotIntent,
    IntentResult,
    coerce_intent,
)
from main.appodus_utils.integrations.intent.prompt import (
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFIER_TOOL_DESCRIPTION,
    intent_vocabulary,
)

logger = di["logger"]

_TOOL_NAME = "classify_intent"
# One closed-set label; there is nothing for a long answer to carry.
_MAX_TOKENS = 256


def _tool_schema() -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": CLASSIFIER_TOOL_DESCRIPTION,
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": sorted(i.value for i in CLASSIFIABLE_INTENTS),
                    "description": intent_vocabulary(),
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "How confident you are, 0 to 1. Answer honestly and low when the "
                        "message is ambiguous — a low score routes the customer to a "
                        "human, which is always an acceptable outcome."
                    ),
                },
            },
            "required": ["intent", "confidence"],
            "additionalProperties": False,
        },
    }


@inject
class ClaudeIntentClassifier(IIntentClassifier):
    """Classifies free text with Claude, behind the provider facade."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    @property
    def platform(self) -> IntentProvider:
        return IntentProvider.ANTHROPIC

    def _get_client(self) -> Optional[Any]:
        """Build the SDK client on first use.

        Lazily, because this provider is constructed at import time in every environment
        — including the ones with no API key — and a classifier that cannot reach a model
        must degrade to human routing, not break the process that imports it.
        """
        if self._client is not None:
            return self._client
        api_key = (settings.INTENT_API_KEY or "").strip()
        if not api_key or api_key == SECRET_PLACEHOLDER:
            logger.warning(
                "INTENT_PROVIDER=anthropic but INTENT_API_KEY is unset — "
                "every free-text turn will route to a human."
            )
            return None
        try:
            from anthropic import AsyncAnthropic
        except ImportError:  # pragma: no cover — the package ships in requirements.txt
            logger.error("The 'anthropic' package is not installed; intent falls back to human routing.")
            return None
        self._client = AsyncAnthropic(
            api_key=api_key, timeout=settings.INTENT_TIMEOUT_SECONDS, max_retries=1
        )
        return self._client

    async def classify(self, text: str) -> IntentResult:
        message = (text or "").strip()
        if not message:
            return IntentResult.unknown(self.platform)

        client = self._get_client()
        if client is None:
            return IntentResult.unknown(self.platform)

        try:
            response = await client.messages.create(
                model=settings.INTENT_MODEL,
                max_tokens=_MAX_TOKENS,
                system=CLASSIFIER_SYSTEM_PROMPT,
                tools=[_tool_schema()],
                # Forced, so the model answers with a label rather than a sentence about
                # a label. There is no useful prose response to this question.
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": message}],
            )
        except Exception as e:  # noqa: BLE001 — every failure has one answer: route to a human
            logger.warning("Intent classification failed ({}); routing to a human.", e)
            return IntentResult.unknown(self.platform)

        return self._read(response)

    def _read(self, response: Any) -> IntentResult:
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) != "tool_use" or block.name != _TOOL_NAME:
                continue
            payload = block.input if isinstance(block.input, dict) else {}
            intent = coerce_intent(payload.get("intent"))
            if intent == BotIntent.UNKNOWN:
                return IntentResult.unknown(self.platform)
            return IntentResult(
                intent=intent,
                confidence=_read_confidence(payload.get("confidence")),
                provider=self.platform,
            )
        return IntentResult.unknown(self.platform)


def _read_confidence(raw: object) -> float:
    """Clamp the model's self-report into 0–1; an unreadable score reads as zero.

    Zero means the caller's confidence gate rejects it, which routes to a human — the
    right answer for a classifier whose own output we could not parse.
    """
    try:
        return max(0.0, min(1.0, float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
