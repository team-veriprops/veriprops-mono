"""Deterministic WhatsApp transport (PRD §26, D43, WA-05, WA-10).

The stub is what CI and the e2e suite run on, so it has to be a faithful stand-in: it
records what would have gone out (so assertions can read it back) and it enforces the
same outbound rules as the live provider — above all the standing "Veriprops never sends
voice notes" rule, which must fail at the transport, not merely in bot copy.
"""
from __future__ import annotations

import pytest

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
    WhatsappMediaType,
    WhatsappPayload,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.stub import (
    WhatsAppStubProvider,
    whatsapp_outbox,
)


@pytest.fixture(autouse=True)
def clear_outbox():
    whatsapp_outbox.clear()
    yield
    whatsapp_outbox.clear()


def message(**payload_kwargs) -> UpsertMessageDto:
    return UpsertMessageDto(
        to={"recipient": "2348012345678"},
        channel=MessageChannel.WHATSAPP,
        payload=WhatsappPayload(**payload_kwargs),
    )


class TestStubSend:
    async def test_records_the_message_and_marks_it_sent(self):
        provider = WhatsAppStubProvider()
        result = await provider.send_message(message(text="Welcome to Veriprops"))

        assert result.status == MessageStatus.SENT
        assert result.provider == MessageProviderName.WHATSAPP_STUB
        assert result.provider_id  # a stand-in wamid, so bookkeeping has a handle

        [recorded] = whatsapp_outbox.all()
        assert recorded.to == "2348012345678"
        assert recorded.text == "Welcome to Veriprops"

    async def test_records_template_sends_so_milestones_are_assertable(self):
        provider = WhatsAppStubProvider()
        await provider.send_message(
            message(template_name="payment_confirmed", template_variables={"1": "VP-1042"})
        )
        [recorded] = whatsapp_outbox.all()
        assert recorded.template_name == "payment_confirmed"
        assert recorded.template_variables == {"1": "VP-1042"}

    async def test_keeps_only_the_most_recent_messages(self):
        # A long-running dev server must not grow an unbounded in-process log.
        provider = WhatsAppStubProvider()
        for i in range(whatsapp_outbox.max_size + 10):
            await provider.send_message(message(text=f"m{i}"))
        assert len(whatsapp_outbox.all()) == whatsapp_outbox.max_size
        assert whatsapp_outbox.all()[-1].text == f"m{whatsapp_outbox.max_size + 9}"

    async def test_filters_the_outbox_by_recipient(self):
        provider = WhatsAppStubProvider()
        await provider.send_message(message(text="for-a"))
        other = message(text="for-b")
        other.to.recipient = "2348029999999"
        await provider.send_message(other)

        assert [m.text for m in whatsapp_outbox.for_recipient("2348029999999")] == ["for-b"]


class TestOutboundVoiceBan:
    async def test_refuses_to_send_audio(self):
        # PRD §26.1.5: Veriprops never sends voice notes. Enforced at the transport so no
        # future flow can bypass it.
        provider = WhatsAppStubProvider()
        with pytest.raises(ValueError, match="voice"):
            await provider.send_message(
                message(media_url="https://example.com/a.ogg", media_type=WhatsappMediaType.AUDIO)
            )
        assert whatsapp_outbox.all() == []


class TestEnvironmentGuard:
    async def test_refuses_to_run_in_production(self, monkeypatch):
        # Defence in depth behind the WHATSAPP_PROVIDER startup validator.
        from main.app.config import settings as settings_module

        monkeypatch.setattr(settings_module.settings, "ENVIRONMENT", Environment.PRODUCTION)
        provider = WhatsAppStubProvider()
        with pytest.raises(ValueError, match="production"):
            await provider.send_message(message(text="hi"))
