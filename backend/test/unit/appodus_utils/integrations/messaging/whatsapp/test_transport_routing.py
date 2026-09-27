"""WhatsApp transport selection (PRD §26, D43).

The rule table is the mechanism behind the determinism contract, so it is asserted
directly: whichever provider the settings name is the one that receives the send, and
neither can fall back to the other — a live send must never silently become a recorded
stub send, nor the reverse.
"""
from __future__ import annotations

import pytest
from kink import di

from main.app.config.settings import settings
from main.appodus_utils.config.settings import WhatsAppProvider
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    WhatsappPayload,
)
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.router import MessageRouter


@pytest.fixture
def router() -> MessageRouter:
    return di[MessageRouter]


def whatsapp_message() -> UpsertMessageDto:
    return UpsertMessageDto(
        to={"recipient": "2348012345678"},
        channel=MessageChannel.WHATSAPP,
        payload=WhatsappPayload(text="hello"),
    )


class TestWhatsAppRouting:
    def test_both_transports_are_registered(self, router):
        registered = {r.provider.name for r in router.providers[MessageChannel.WHATSAPP]}
        assert {
            MessageProviderName.WHATSAPP_STUB,
            MessageProviderName.WHATSAPP_BUSINESS,
        } <= registered

    def test_stub_setting_selects_the_stub(self, router, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", WhatsAppProvider.STUB)
        assert router._select_provider(whatsapp_message()).name == MessageProviderName.WHATSAPP_STUB

    def test_meta_setting_selects_the_live_cloud_api(self, router, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", WhatsAppProvider.META)
        assert (
            router._select_provider(whatsapp_message()).name
            == MessageProviderName.WHATSAPP_BUSINESS
        )

    def test_neither_transport_falls_back_to_the_other(self, router):
        # Exclusive rules: a failing live send must surface, not quietly get recorded by
        # the stub (and a stub failure must never reach Meta).
        rules = router.routing_rules[MessageChannel.WHATSAPP]["rules"]
        assert all(rule["exclusive"] and rule["fallback_order"] == [] for rule in rules)

    def test_an_open_live_circuit_never_turns_a_send_into_a_stub_send(self, router, monkeypatch):
        # With the Cloud API's breaker open, selection must still name the Cloud API (the send
        # then fails loudly) rather than fall through to a default that records it in the stub.
        from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", WhatsAppProvider.META)
        monkeypatch.setattr(
            resilience_manager, "get_circuit_state",
            lambda name: {"open": name == MessageProviderName.WHATSAPP_BUSINESS},
        )
        assert (
            router._select_provider(whatsapp_message()).name
            == MessageProviderName.WHATSAPP_BUSINESS
        )

    def test_no_default_route_names_the_stub(self, router):
        assert MessageProviderName.WHATSAPP_STUB not in router.routing_rules[MessageChannel.WHATSAPP]["default"]
