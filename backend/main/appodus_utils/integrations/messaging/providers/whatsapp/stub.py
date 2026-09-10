"""Deterministic WhatsApp transport (PRD §26, D43).

The live Cloud API provider needs Meta Business verification, an approved template set,
and a bound phone number — none of which an automated run can have. This provider stands
in for it: sends are recorded in an in-process outbox that dev endpoints and the e2e
suite read back, so the entire channel (bot replies, milestone templates, handoff links)
is exercisable end to end without a single call to Meta.

It is a stand-in, not a mock: the outbound rules that matter are enforced here too, so a
flow that would be rejected live is rejected in CI as well.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Deque, Dict, List, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils import Object, Utils
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
    WhatsappPayload,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.providers.whatsapp.outbound import (
    assert_no_outbound_voice,
)

logger = di["logger"]


class StubOutboundMessage(Object):
    """One recorded send — the shape assertions and the dev outbox endpoint read."""

    wamid: str
    to: str
    text: Optional[str] = None
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    # The OTP button's value on an authentication template — recorded because it is a
    # required component of the live send, so a stub run has to be able to prove it.
    template_button_parameter: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    buttons: List[str] = []
    sent_at: Optional[datetime] = None


class WhatsAppOutbox:
    """Bounded in-process record of stub sends.

    Bounded because a dev server can run for days: this is a debugging and assertion
    aid, never a durable store — the `messages` table remains the bookkeeping record.
    """

    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self._messages: Deque[StubOutboundMessage] = deque(maxlen=max_size)

    def record(self, message: StubOutboundMessage) -> None:
        self._messages.append(message)

    def all(self) -> List[StubOutboundMessage]:
        return list(self._messages)

    def for_recipient(self, recipient: str) -> List[StubOutboundMessage]:
        return [m for m in self._messages if m.to == recipient]

    def latest(self, recipient: Optional[str] = None) -> Optional[StubOutboundMessage]:
        messages = self.for_recipient(recipient) if recipient else self.all()
        return messages[-1] if messages else None

    def clear(self) -> None:
        self._messages.clear()


whatsapp_outbox = WhatsAppOutbox()


@inject
class WhatsAppStubProvider(IMessageProvider):
    """Records outbound WhatsApp messages instead of sending them."""

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.WHATSAPP_STUB

    @property
    def supported_channels(self) -> List[MessageChannel]:
        return [MessageChannel.WHATSAPP]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def get_message_status(self, message_id: str) -> Optional[str]:
        # Mirrors the live provider: Cloud API pushes delivery state by webhook.
        return None

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        if settings.ENVIRONMENT == Environment.PRODUCTION:
            raise ValueError(
                "WhatsAppStubProvider must never serve production traffic. "
                "Set WHATSAPP_PROVIDER=meta."
            )

        payload: WhatsappPayload = message.payload
        assert_no_outbound_voice(payload)

        recipient = message.to.recipient
        to = recipient if isinstance(recipient, str) else ", ".join(recipient)
        sent_at = Utils.datetime_now()
        # A stand-in for Meta's wamid so bookkeeping and dedup have a handle to hold.
        wamid = f"wamid.stub.{Utils.random_str(16)}"

        whatsapp_outbox.record(StubOutboundMessage(
            wamid=wamid,
            to=to,
            text=payload.text,
            template_name=payload.template_name,
            template_variables=payload.template_variables,
            template_button_parameter=payload.template_button_parameter,
            media_url=str(payload.media_url) if payload.media_url else None,
            media_type=payload.media_type.value if payload.media_type else None,
            buttons=[b.title for b in (payload.buttons or [])],
            sent_at=sent_at,
        ))

        logger.info(
            "[WhatsAppStubProvider] recorded outbound to {} (template={}, chars={})",
            to, payload.template_name, len(payload.text or ""),
        )

        message.sent_at = sent_at
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = wamid
        return message
