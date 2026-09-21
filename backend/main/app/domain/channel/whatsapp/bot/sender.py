"""How a bot reply leaves the building (PRD §26.6, §26.8, Decision K).

A bot reply is free text answering a message that just arrived, so it is inside Meta's
24-hour window by construction and needs no template — the §26.7 registry is for
business-initiated sends, which is the opposite case.

Every reply goes out **twice, deliberately**: once over WhatsApp to the customer, and once
into the conversation as a `SYSTEM` message so the admin console shows the same thread the
customer sees. Decision K's "one console, one thread" only holds if the bot's own half of
the dialogue is in it — an agent taking over mid-conversation has to be able to read what
the bot already said.

Sending is best-effort and never raises. The customer's message has already been recorded
and answered as far as our own state is concerned; turning a delivery failure into a 500
would make Meta redeliver the *inbound* message, and the customer would be answered twice.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.communication.chat_message.models import (
    ChatMessage,
    MessageKind,
    MessageSource,
    SenderKind,
)
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import Conversation
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    WhatsappPayload,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_wa_recipient
from main.appodus_utils.integrations.messaging.service import MessagingService

logger: Logger = di["logger"]


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppBotSender:
    def __init__(
        self,
        messaging_service: MessagingService,
        chat_message_service: ChatMessageService,
        chat_message_repo: ChatMessageRepo,
    ):
        self._messaging_service = messaging_service
        self._chat_message_service = chat_message_service
        self._chat_message_repo = chat_message_repo

    async def reply(self, conversation: Conversation, phone_e164: str, text: str) -> ChatMessage:
        """Send one bot reply to the customer and mirror it into the console thread.

        The console copy keeps the wamid of what went out, so Meta's receipts for the reply
        show on the message an agent reads (D92).
        """
        mirrored = await self._mirror_to_console(conversation, text)
        wamid = await self._deliver(phone_e164, text)
        if wamid is not None:
            self._chat_message_repo.mark_channel_sent(mirrored, wamid, Utils.datetime_now())
        return mirrored

    async def _mirror_to_console(self, conversation: Conversation, text: str) -> ChatMessage:
        """Put the bot's words in the thread an agent reads.

        `SenderKind.SYSTEM` is what exempts this from the fraud scan: bot copy carries
        `veriprops.ng` links and the official WhatsApp number by design, and the URL and
        social rules match both — scanning it would hold the very messages that keep a
        customer oriented.
        """
        return await self._chat_message_service.send(
            conversation,
            None,
            SenderKind.SYSTEM,
            text,
            kind=MessageKind.SYSTEM_AUTO,
            source=MessageSource.WHATSAPP,
        )

    async def _deliver(self, phone_e164: str, text: str) -> Optional[str]:
        """Hand the text to whichever transport `WHATSAPP_PROVIDER` selected. Returns Meta's
        id for what went out (empty when the transport gave none), or ``None`` if nothing did."""
        if not settings.ENABLE_OUT_MESSAGING:
            # Same posture as the rest of the messaging pipeline: the console mirror above
            # still happened, so a local run without outbound enabled is fully inspectable.
            logger.warning(
                "Bot reply not dispatched (ENABLE_OUT_MESSAGING=False): "
                f"recipient={to_wa_recipient(phone_e164)}"
            )
            return None
        try:
            result = await self._messaging_service.send_message(
                MessageRequest(
                    channel=MessageChannel.WHATSAPP,
                    to=MessageRecipient(recipient=to_wa_recipient(phone_e164)),
                    payload=WhatsappPayload(text=text),
                )
            )
            return result.provider_id or ""
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(f"Bot reply delivery failed for {to_wa_recipient(phone_e164)}: {exc}")
            return None
