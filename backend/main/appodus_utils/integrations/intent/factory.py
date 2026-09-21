"""Resolves the active intent classifier from ``settings.INTENT_PROVIDER`` (D48/D53).

Same shape as ``KycProviderFactory``: every ``IIntentClassifier`` subclass is registered,
so selecting a provider is a runtime setting rather than a wiring change. An unrecognised
selection falls back to the deterministic stub — never to nothing, because a missing
classifier would make every free-text turn raise instead of routing to a human.
"""
from typing import List

from kink import inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import settings
from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.interface import IIntentClassifier

di_bootstrap.register_all_subclasses(IIntentClassifier)


@inject
class IntentClassifierFactory:
    def __init__(self, classifiers: List[IIntentClassifier]):
        self._classifiers = classifiers
        self._factory = {c.platform: c for c in classifiers}

    def get_active_classifier(self) -> IIntentClassifier:
        selected = IntentProvider(settings.INTENT_PROVIDER)
        return self._factory.get(selected) or self._factory[IntentProvider.STUB]

    def get_classifier(self, provider: IntentProvider) -> IIntentClassifier:
        return self._factory.get(provider)
