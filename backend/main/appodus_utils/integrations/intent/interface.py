"""Intent classifier facade (PRD §7.6, D48).

Swappable behind ``settings.INTENT_PROVIDER``, mirroring the KYC and messaging provider
facades. Implementations wrap a live model or the deterministic keyword table.

**A classifier never raises.** Timeouts, transport errors, malformed answers and
off-vocabulary answers all resolve to ``IntentResult.unknown()``, because the caller's
response to every one of them is identical: route the conversation to a human (§7.6.4).
Letting a provider hiccup propagate would turn "we could not classify this" into "the bot
stopped replying", which §7.6.5 exists to prevent.
"""
from abc import ABC, abstractmethod

from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.models import IntentResult


class IIntentClassifier(ABC):
    @property
    @abstractmethod
    def platform(self) -> IntentProvider:
        ...

    @abstractmethod
    async def classify(self, text: str) -> IntentResult:
        """Map a customer's free text onto the closed ``BotIntent`` set.

        Returns ``UNKNOWN`` rather than raising on any failure.
        """
        ...
