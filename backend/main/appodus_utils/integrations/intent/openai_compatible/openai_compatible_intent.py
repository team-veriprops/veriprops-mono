"""Generic OpenAI-compatible intent classifier (D48/D53).

One adapter for every provider that speaks the `/chat/completions` shape — OpenAI,
DeepSeek, Groq, Together, a local Ollama — because that shape is the closest thing the
field has to a lingua franca. Point ``INTENT_API_BASE_URL`` at the provider, name the
model, supply the key: switching provider is a config change, which is the whole point of
the facade being provider-agnostic.

Raw HTTP over the shared `httpx` client rather than a vendor SDK: this is one POST, and
the adapter exists precisely so that no single vendor's package is a dependency of the
channel.

The answer is constrained by asking for JSON and then validating it — `response_format`
support is uneven across compatible providers, so the parse is written to survive its
absence (a fenced or chatty reply is still read). Anything unreadable becomes ``UNKNOWN``,
which routes to a human.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from httpx import AsyncClient
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
    intent_vocabulary,
)

logger = di["logger"]

_MAX_TOKENS = 256
# The JSON object the model is asked for. Spelled out in the prompt rather than left to
# `response_format`, which not every compatible provider implements.
_OUTPUT_INSTRUCTION = (
    "Reply with a JSON object and nothing else, in the form "
    '{{"intent": "<LABEL>", "confidence": <0 to 1>}}. '
    "The label must be exactly one of: {labels}."
)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _system_prompt() -> str:
    labels = ", ".join(sorted(i.value for i in CLASSIFIABLE_INTENTS))
    return (
        f"{CLASSIFIER_SYSTEM_PROMPT}\n\n"
        f"{_OUTPUT_INSTRUCTION.format(labels=labels)}\n\n"
        f"What the labels mean — {intent_vocabulary()}"
    )


@inject
class OpenAiCompatibleIntentClassifier(IIntentClassifier):
    """Classifies free text against any `/chat/completions` provider."""

    @property
    def platform(self) -> IntentProvider:
        return IntentProvider.OPENAI_COMPATIBLE

    async def classify(self, text: str) -> IntentResult:
        message = (text or "").strip()
        if not message:
            return IntentResult.unknown(self.platform)

        base_url = (settings.INTENT_API_BASE_URL or "").strip().rstrip("/")
        api_key = (settings.INTENT_API_KEY or "").strip()
        if not base_url or not api_key or api_key == SECRET_PLACEHOLDER:
            logger.warning(
                "INTENT_PROVIDER=openai_compatible needs INTENT_API_BASE_URL and "
                "INTENT_API_KEY — every free-text turn will route to a human."
            )
            return IntentResult.unknown(self.platform)

        client: AsyncClient = di[AsyncClient]
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.INTENT_MODEL,
                    "max_tokens": _MAX_TOKENS,
                    # A label is not a creative task; determinism also makes an incident
                    # reproducible.
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": _system_prompt()},
                        {"role": "user", "content": message},
                    ],
                },
                timeout=settings.INTENT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as e:  # noqa: BLE001 — every failure has one answer: route to a human
            logger.warning("Intent classification failed ({}); routing to a human.", e)
            return IntentResult.unknown(self.platform)

        return self._read(body)

    def _read(self, body: Any) -> IntentResult:
        payload = _parse_answer(_first_message_content(body))
        if payload is None:
            return IntentResult.unknown(self.platform)
        intent = coerce_intent(payload.get("intent"))
        if intent == BotIntent.UNKNOWN:
            return IntentResult.unknown(self.platform)
        return IntentResult(
            intent=intent,
            confidence=_read_confidence(payload.get("confidence")),
            provider=self.platform,
        )


def _first_message_content(body: Any) -> str:
    try:
        return str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return ""


def _parse_answer(content: str) -> Optional[dict]:
    """Read the JSON object out of a reply that may be fenced or prefaced with prose."""
    if not content.strip():
        return None
    match = _JSON_OBJECT.search(content)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_confidence(raw: object) -> float:
    """Clamp the model's self-report into 0–1; an unreadable score reads as zero."""
    try:
        return max(0.0, min(1.0, float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
