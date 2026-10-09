"""TermiiSMSProvider's request contract.

Termii's API documents the recipient as digits in international form with no leading
``+``. Our recipients are E.164 (``+234…``), so the provider converts at its own boundary,
the way the WhatsApp seam does. The rate-limit key keeps the E.164 form, because that is how
the rest of the messaging layer names a recipient.
"""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.exception.exceptions import IntegrationRateLimitException
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
    SmsPayload,
)
from main.appodus_utils.integrations.messaging.providers.sms.termii import TermiiSMSProvider

NUMBER = "+2348031234567"


def _sms() -> UpsertMessageDto:
    return UpsertMessageDto.from_request(MessageRequest(
        channel=MessageChannel.SMS,
        to=MessageRecipient(recipient=NUMBER),
        payload=SmsPayload(text="Your code is 123456", sender_id="Veriprops"),
        extras={"user_id": "u-1"},
    ))


def _provider(status_code: int, body: dict | None = None) -> TermiiSMSProvider:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = ""
    response.json.return_value = body or {}
    provider = TermiiSMSProvider()
    provider.client = MagicMock()
    provider.client.post = AsyncMock(return_value=response)
    return provider


async def test_the_recipient_goes_to_termii_as_digits_only():
    provider = _provider(200, {"code": "ok", "message_id": "tm-1"})

    sent = await provider.send_message(_sms())

    body = provider.client.post.await_args.kwargs["json"]
    assert body["to"] == "2348031234567"
    assert (sent.status, sent.provider_id) == (MessageStatus.SENT, "tm-1")


async def test_a_rate_limit_names_the_recipient_in_e164():
    provider = _provider(429)

    with pytest.raises(IntegrationRateLimitException) as exc:
        await provider.send_message(_sms())

    assert exc.value.key == NUMBER
