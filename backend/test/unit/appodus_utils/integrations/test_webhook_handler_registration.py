"""Webhook handler registration guard.

`WebhookHandlerFactory` builds its routing table from `BaseWebhookHandler.__subclasses__()`
at import time, so a handler class that nothing imports is simply invisible: the endpoint
answers "platform 'X' not supported" and the integration is silently dead. Unit tests that
instantiate a handler directly cannot see this — they import the module themselves.

That is not hypothetical. The WhatsApp handler shipped unimported and its webhook, the
public entry point for the entire channel, was unreachable until a live drive-through hit
it. Each integration package imports its own handler to prevent this; the test below is
what makes that convention enforceable.
"""
from __future__ import annotations

import pytest
from kink import di

# `main.app.domain` is the app's single aggregation point — importing it is what pulls in
# every integration package, exactly as the running app does. The registration table is
# built from whatever is imported at that moment, so the assertion below is only
# meaningful against a fully-loaded app.
import main.app.domain  # noqa: F401
from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.integrations.factory import WebhookHandlerFactory

# Platforms that terminate an inbound webhook. A platform listed here must resolve to a
# handler; add the entry when you add the integration, and the missing import fails here
# rather than in production.
_WEBHOOK_PLATFORMS = [
    IntegratedPlatform.PAYSTACK,
    IntegratedPlatform.FLUTTERWAVE,
    IntegratedPlatform.ZOHO_DOC_SIGN,
    IntegratedPlatform.GOOGLE_DRIVE,
    IntegratedPlatform.WHATSAPP,
]


@pytest.mark.parametrize("platform", _WEBHOOK_PLATFORMS, ids=lambda p: p.value)
def test_every_webhook_platform_resolves_to_a_registered_handler(platform):
    factory: WebhookHandlerFactory = di[WebhookHandlerFactory]
    handler = factory.get_handler(platform)
    assert handler is not None, (
        f"No webhook handler registered for '{platform.value}'. The class exists but "
        "nothing imports it, so BaseWebhookHandler.__subclasses__() never sees it and "
        "the endpoint answers 'platform not supported'. Import it from its integration "
        "package's __init__.py, as the other integrations do."
    )
    assert handler.platform == platform


def test_no_two_platforms_share_a_handler():
    """A duplicated `platform` property would silently shadow another integration."""
    factory: WebhookHandlerFactory = di[WebhookHandlerFactory]
    platforms = [h.platform for h in factory.get_handlers()]
    assert len(platforms) == len(set(platforms)), f"duplicate platforms: {platforms}"
