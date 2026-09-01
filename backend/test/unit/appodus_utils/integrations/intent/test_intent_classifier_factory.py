"""Provider-registration guard for the intent facade (D48/D53).

`IntentClassifierFactory` builds its table from `IIntentClassifier.__subclasses__()`, so
an adapter class that nothing imports is invisible — selecting it in config would silently
fall back to the keyword table, halving the bot's free-text coverage with no error and
nothing in the logs. That is the same failure the WhatsApp webhook handler shipped with,
found only by a live drive-through; this test is what makes the import convention
enforceable instead of remembered.
"""
from __future__ import annotations

import pytest
from kink import di

# The app's single aggregation point — importing it loads every integration package,
# exactly as the running app does. The table is only meaningful against a loaded app.
import main.app.domain  # noqa: F401
from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.factory import IntentClassifierFactory


@pytest.mark.parametrize("provider", list(IntentProvider), ids=lambda p: p.value)
def test_every_declared_provider_resolves_to_a_registered_classifier(provider):
    factory: IntentClassifierFactory = di[IntentClassifierFactory]

    classifier = factory.get_classifier(provider)

    assert classifier is not None, (
        f"IntentProvider.{provider.name} has no registered adapter — check that its class "
        f"is imported by appodus_utils/integrations/intent/__init__.py."
    )
    assert classifier.platform == provider


def test_active_classifier_is_the_stub_under_test():
    """`ENVIRONMENT=test` pins the provider; this is the assertion that says so out loud."""
    factory: IntentClassifierFactory = di[IntentClassifierFactory]

    assert factory.get_active_classifier().platform == IntentProvider.STUB


def test_unknown_selection_degrades_to_the_stub_rather_than_to_nothing(monkeypatch):
    """A missing classifier would make every free-text turn raise instead of routing to a
    human — the keyword table is the floor, not `None`."""
    from main.app.config.settings import settings

    factory: IntentClassifierFactory = di[IntentClassifierFactory]
    monkeypatch.setattr(settings, "INTENT_PROVIDER", IntentProvider.ANTHROPIC, raising=False)
    monkeypatch.delitem(factory._factory, IntentProvider.ANTHROPIC, raising=False)

    assert factory.get_active_classifier().platform == IntentProvider.STUB
