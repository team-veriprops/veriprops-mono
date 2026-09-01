"""`UpsertMessageDto.from_request` — the seam between a send request and its bookkeeping row.

Every dispatch crosses this conversion, and a mismatch here fails **silently**: the
messaging service catches the error, logs it, and the caller sees a send that simply never
arrived. The bot's first free-text reply was lost exactly that way — `MessageRequest.extras`
is optional, the DTO's is a required dict, and `model_dump` emits an explicit `None` that
pydantic will not replace with a default.

The tests below cover both construction routes, because only one of them was ever
exercised before: the builder always sets `extras`, so the bug lived entirely in the
direct-construction path the model's own docstring documents as supported.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    SmsPayload,
    WhatsappPayload,
)


def _whatsapp_request(**overrides) -> MessageRequest:
    """A free-text WhatsApp send, the shape a bot reply builds directly."""
    fields = {
        "channel": MessageChannel.WHATSAPP,
        "to": MessageRecipient(recipient="2348012345678"),
        "payload": WhatsappPayload(text="Hello 👋"),
    }
    fields.update(overrides)
    return MessageRequest(**fields)


def test_a_directly_constructed_request_converts():
    """The regression. Nothing is set beyond the required fields — which is precisely
    what a bot reply sends, and what used to raise."""
    dto = UpsertMessageDto.from_request(_whatsapp_request())

    assert dto.channel == MessageChannel.WHATSAPP
    assert dto.extras == {}


def test_explicit_extras_survive():
    dto = UpsertMessageDto.from_request(_whatsapp_request(extras={"campaign_id": "x"}))

    assert dto.extras == {"campaign_id": "x"}


def test_an_empty_extras_dict_is_not_confused_with_an_absent_one():
    dto = UpsertMessageDto.from_request(_whatsapp_request(extras={}))

    assert dto.extras == {}


def test_the_schedule_is_carried_under_its_other_name():
    """`schedule_at` → `scheduled_at`. A raw dump drops it, and the message would be sent
    immediately instead of when it was asked for."""
    when = datetime.now(timezone.utc) + timedelta(hours=1)

    dto = UpsertMessageDto.from_request(_whatsapp_request(schedule_at=when))

    assert dto.scheduled_at == when


def test_the_expiry_horizon_survives():
    """Time-bound content (OTPs, reset links) must never be re-dispatched past this."""
    horizon = datetime.now(timezone.utc) + timedelta(minutes=10)

    dto = UpsertMessageDto.from_request(_whatsapp_request(expires_at=horizon))

    assert dto.expires_at == horizon


@pytest.mark.parametrize(
    "channel, payload, recipient",
    [
        (MessageChannel.WHATSAPP, WhatsappPayload(text="hi"), "2348012345678"),
        (MessageChannel.SMS, SmsPayload(message="hi"), "+2348012345678"),
    ],
    ids=["whatsapp", "sms"],
)
def test_every_direct_channel_construction_converts(channel, payload, recipient):
    """A conversion that works for one channel and not another would be found only in
    production, by the channel nobody tested."""
    request = MessageRequest(
        channel=channel, to=MessageRecipient(recipient=recipient), payload=payload
    )

    assert UpsertMessageDto.from_request(request).channel == channel


def test_the_builder_route_still_converts():
    """The path that already worked — kept so a fix to the direct route cannot break it."""
    request = (
        MessageRequest.builder()
        .channel(MessageChannel.WHATSAPP)
        .to(MessageRecipient(recipient="2348012345678"))
        .payload(WhatsappPayload(text="Hello 👋"))
        .build()
    )

    assert UpsertMessageDto.from_request(request).extras == {}
