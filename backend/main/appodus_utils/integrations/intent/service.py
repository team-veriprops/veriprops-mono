"""The one place a classifier's answer becomes an intent the bot will act on.

Two rules live here rather than in each adapter, so they cannot drift between providers:

* **The confidence gate.** Below ``INTENT_MIN_CONFIDENCE`` the answer is discarded and the
  turn becomes ``UNKNOWN`` — §26.6.4's "low-confidence intent → human routing, never a
  guess", enforced once.
* **Failure is not an exception.** Adapters already resolve their own errors to
  ``UNKNOWN``; this service keeps that contract at the boundary the bot engine sees, so
  no caller has to wrap a classify call in a try block to stay safe.
"""
from __future__ import annotations

from kink import inject

from main.app.config.settings import settings
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.intent.factory import IntentClassifierFactory
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class IntentService:
    def __init__(self, intent_classifier_factory: IntentClassifierFactory):
        self._intent_classifier_factory = intent_classifier_factory

    async def classify(self, text: str) -> IntentResult:
        """Classify a customer's free text, or answer ``UNKNOWN``."""
        classifier = self._intent_classifier_factory.get_active_classifier()
        result = await classifier.classify(text)
        if result.intent == BotIntent.UNKNOWN:
            return result
        if result.confidence < settings.INTENT_MIN_CONFIDENCE:
            # Recognised, but not well enough to act on. Keeping the provider on the
            # result lets §26.10 tell "the bot doesn't cover this" from "the model was
            # unsure" when the escalation rate is read.
            return IntentResult.unknown(result.provider)
        return result
