"""Meta Cloud API inbound normalization (PRD §7.3.3, WA-09).

Meta's webhook envelope is deeply nested and carries several payload shapes on one
endpoint. Everything downstream — the bot engine, the console adapter, the fraud scan —
reads the normalized form, so these tests pin the translation rather than the envelope.
"""
from __future__ import annotations

from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    normalize_webhook,
)


def envelope(*messages, statuses=None, contacts=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"}}
    if messages:
        value["messages"] = list(messages)
    if statuses:
        value["statuses"] = statuses
    if contacts:
        value["contacts"] = contacts
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": value}]}]}


TEXT = {
    "from": "2348012345678",
    "id": "wamid.TEXT1",
    "timestamp": "1756600000",
    "type": "text",
    "text": {"body": "  How much for a Lagos land check?  "},
}


class TestTextMessages:
    def test_normalizes_a_text_message(self):
        [msg] = normalize_webhook(envelope(TEXT))
        assert msg.wamid == "wamid.TEXT1"
        assert msg.from_phone == "+2348012345678"  # E.164, as identity lookups expect
        assert msg.kind == InboundKind.TEXT
        assert msg.text == "How much for a Lagos land check?"  # trimmed
        assert msg.received_at is not None

    def test_carries_the_sender_profile_name_when_meta_supplies_it(self):
        contacts = [{"wa_id": "2348012345678", "profile": {"name": "Ada"}}]
        [msg] = normalize_webhook(envelope(TEXT, contacts=contacts))
        assert msg.sender_name == "Ada"

    def test_returns_every_message_in_a_batched_delivery(self):
        second = {**TEXT, "id": "wamid.TEXT2", "text": {"body": "Second"}}
        assert [m.wamid for m in normalize_webhook(envelope(TEXT, second))] == [
            "wamid.TEXT1",
            "wamid.TEXT2",
        ]


class TestInteractiveReplies:
    def test_a_button_reply_reads_as_its_payload_id(self):
        # Menu selections must not depend on the button's display copy.
        message = {
            "from": "2348012345678", "id": "wamid.BTN", "timestamp": "1756600000",
            "type": "interactive",
            "interactive": {"type": "button_reply",
                            "button_reply": {"id": "menu_status", "title": "Check my status"}},
        }
        [msg] = normalize_webhook(envelope(message))
        assert msg.kind == InboundKind.INTERACTIVE
        assert msg.interactive_id == "menu_status"
        assert msg.text == "Check my status"

    def test_a_list_reply_reads_the_same_way(self):
        message = {
            "from": "2348012345678", "id": "wamid.LIST", "timestamp": "1756600000",
            "type": "interactive",
            "interactive": {"type": "list_reply",
                            "list_reply": {"id": "faq_pricing", "title": "Pricing"}},
        }
        [msg] = normalize_webhook(envelope(message))
        assert msg.interactive_id == "faq_pricing"


class TestNonTextMessages:
    def test_media_carries_its_id_and_caption(self):
        message = {
            "from": "2348012345678", "id": "wamid.IMG", "timestamp": "1756600000",
            "type": "image",
            "image": {"id": "MEDIA123", "mime_type": "image/jpeg", "caption": "my survey plan"},
        }
        [msg] = normalize_webhook(envelope(message))
        assert msg.kind == InboundKind.IMAGE
        assert msg.media_id == "MEDIA123"
        assert msg.media_mime_type == "image/jpeg"
        assert msg.text == "my survey plan"

    def test_voice_notes_are_distinguishable_for_the_audio_routing_rule(self):
        # §7.6.3: voice notes are acknowledged and routed to a human, never dropped —
        # and §7.10 counts their volume as the v1.1 transcription trigger.
        message = {
            "from": "2348012345678", "id": "wamid.AUD", "timestamp": "1756600000",
            "type": "audio", "audio": {"id": "AUD1", "mime_type": "audio/ogg", "voice": True},
        }
        [msg] = normalize_webhook(envelope(message))
        assert msg.kind == InboundKind.AUDIO

    def test_location_and_contacts_normalize_without_text(self):
        pin = {"from": "2348012345678", "id": "wamid.LOC", "timestamp": "1756600000",
               "type": "location", "location": {"latitude": 6.5, "longitude": 3.3}}
        card = {"from": "2348012345678", "id": "wamid.CON", "timestamp": "1756600000",
                "type": "contacts", "contacts": [{"name": {"formatted_name": "X"}}]}
        kinds = [m.kind for m in normalize_webhook(envelope(pin, card))]
        assert kinds == [InboundKind.LOCATION, InboundKind.CONTACTS]

    def test_an_unknown_type_still_normalizes_so_it_can_be_routed_to_a_human(self):
        # Meta adds message types over time; an unrecognised one must never be dropped.
        message = {"from": "2348012345678", "id": "wamid.NEW", "timestamp": "1756600000",
                   "type": "some_future_type", "some_future_type": {}}
        [msg] = normalize_webhook(envelope(message))
        assert msg.kind == InboundKind.UNSUPPORTED


class TestNonMessagePayloads:
    def test_delivery_status_callbacks_yield_no_inbound_messages(self):
        # Meta posts read/delivered receipts to the same endpoint; they are not inbound.
        statuses = [{"id": "wamid.OUT", "status": "delivered", "recipient_id": "234801"}]
        assert normalize_webhook(envelope(statuses=statuses)) == []

    def test_an_empty_or_foreign_envelope_is_ignored_rather_than_raising(self):
        # The endpoint is public: a malformed body must not be able to 500 it.
        assert normalize_webhook({}) == []
        assert normalize_webhook({"entry": [{"changes": [{"field": "account_update"}]}]}) == []
        assert normalize_webhook({"entry": "not-a-list"}) == []

    def test_a_message_without_an_id_is_skipped(self):
        # The wamid is the dedup key; without it a redelivery would double-post.
        assert normalize_webhook(envelope({**TEXT, "id": ""})) == []
