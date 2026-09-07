"""Inbound WhatsApp ingestion (PRD §26.3.3, §26.8, WA-09/WA-12/WA-13).

Where a Meta delivery becomes an ordinary Veriprops conversation. Two properties matter
more than anything else here:

* **Exactly once.** Meta redelivers until it gets a 2xx, so ingestion is keyed on the
  `wamid`: a repeat is recorded as already-seen and produces no second console message.
  That guarantee is what lets the webhook acknowledge every authenticated delivery.
* **No special path.** A WhatsApp message joins the *same* conversation pipeline as web
  chat, which means it runs the same send-time fraud scan and lands in the same admin
  console (Decision K). The channel changes where a message came from, never how it is
  policed or who mediates it.

Non-text inbound is journalled and surfaced as a labelled placeholder so nothing is
silently dropped (§26.6.3); the policy replies that go back out are the bot engine's job,
which this service hands the turn to once the message is safely recorded.

**Recording comes first, answering second.** The journal row and the console message are
what make the turn idempotent and visible; a bot failure after that point costs a reply,
not the message. The engine has its own §26.6.5 fallback, and anything that still escapes
is logged rather than raised — the webhook must keep acknowledging, or Meta throttles and
eventually disables the subscription.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from kink import di, inject

from main.app.domain.channel.whatsapp.inbound.models import (
    CreateWhatsAppInboundMessageDto,
    WhatsAppInboundMessage,
)
from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.app.domain.communication.chat_message.models import MessageSource, SenderKind
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.communication.conversation.service import ConversationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.attribution import (
    extract_page_code,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    InboundWhatsAppMessage,
)

logger: Logger = di["logger"]

# What the console shows for a message whose content is not text. The customer's own
# words are always shown when there are any (a caption); otherwise the agent sees what
# kind of thing arrived, never an empty bubble.
_PLACEHOLDER_BY_KIND = {
    InboundKind.IMAGE: "[sent an image]",
    InboundKind.DOCUMENT: "[sent a document]",
    InboundKind.VIDEO: "[sent a video]",
    InboundKind.AUDIO: "[sent a voice note]",
    InboundKind.STICKER: "[sent a sticker]",
    InboundKind.LOCATION: "[shared a location pin]",
    InboundKind.CONTACTS: "[shared a contact card]",
    InboundKind.UNSUPPORTED: "[sent an unsupported message type]",
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppInboundService:
    def __init__(
        self,
        whatsapp_inbound_message_repo: WhatsAppInboundMessageRepo,
        conversation_service: ConversationService,
        chat_message_service: ChatMessageService,
    ):
        self._whatsapp_inbound_message_repo = whatsapp_inbound_message_repo
        self._conversations = conversation_service
        self._chat = chat_message_service

    async def ingest(self, message: InboundWhatsAppMessage) -> Optional[WhatsAppInboundMessage]:
        """Record an inbound message and surface it in the admin console.

        Returns the journal row, or ``None`` when this delivery has already been handled.
        """
        already_seen = await self._whatsapp_inbound_message_repo.get_by_wamid(message.wamid)
        if already_seen is not None:
            # A Meta redelivery, not a new turn in the conversation.
            return None

        # §26.4.1's widget marker is metadata the customer's phone typed for them, not words
        # they wrote (D85). It is lifted out **here** rather than in the Meta normalizer
        # because `ingest` is the single funnel every inbound passes through — Meta's
        # webhook and the dev injection door both — and doing it upstream gave the two
        # doors different behaviour, which is exactly what the automation-determinism
        # contract exists to prevent. Everything downstream (the classifier, the
        # guardrails, the console) then reads the message the customer believes they sent;
        # `payload` keeps Meta's original untouched for the §26.8 record.
        page_code, cleaned_text = extract_page_code(message.text)
        if page_code is not None:
            message = message.model_copy(
                update={"text": cleaned_text, "page_code": page_code}
            )

        record = await self._whatsapp_inbound_message_repo.create_return_model(
            CreateWhatsAppInboundMessageDto(
                wamid=message.wamid,
                from_phone=message.from_phone,
                kind=message.kind,
                text=message.text,
                page_code=message.page_code,
                interactive_id=message.interactive_id,
                media_id=message.media_id,
                media_mime_type=message.media_mime_type,
                sender_name=message.sender_name,
                payload=message.raw,
                received_at=message.received_at,
            )
        )

        conversation = await self._conversations.get_or_create_whatsapp_thread(
            message.from_phone, subject=self._subject_for(message)
        )
        chat_message = await self._chat.send(
            conversation,
            # The sender is a phone number, not yet an account. Identity is resolved
            # server-side by the linking flow (§26.4.4) — never claimed by the message.
            None,
            SenderKind.CUSTOMER,
            self._body_for(message),
            source=MessageSource.WHATSAPP,
            external_message_id=message.wamid,
            media_kind=self._media_kind_for(message),
        )

        # Setting these on the attached row rather than re-fetching: the record was
        # created in this same uncommitted transaction.
        record.chat_message_id = Utils.uuid_to_hex(chat_message.id)
        record.processed_at = Utils.datetime_now()
        self._whatsapp_inbound_message_repo._session.add(record)

        await self._flush_queued_replies(conversation)
        await self._answer(message, conversation)
        return record

    async def _flush_queued_replies(self, conversation: Conversation) -> None:
        """Send anything an agent typed while Meta's window was shut (§26.7, WA-41).

        This message just reopened the window, so the queue can go now. It runs **before**
        the bot turn deliberately: the agent's answer was written first and should arrive
        first, and a thread with a queued reply is sticky-`HUMAN` anyway (D57), so the bot
        will not be adding to it.

        Best-effort for the same reason ingestion's other side effects are — the inbound
        message is already journalled, and a failure here must not make Meta redeliver it.
        """
        from main.app.domain.channel.whatsapp.console_sender import WhatsAppConsoleSender

        try:
            await di[WhatsAppConsoleSender].flush(conversation)
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            # Identified by thread id rather than by number: this runs *inside* an except
            # handler, so a log line that could itself raise would replace the real error
            # with an AttributeError about the message we were trying to write.
            logger.error(f"Could not flush queued replies on {conversation.id}: {exc}")

    async def _answer(
        self, message: InboundWhatsAppMessage, conversation: Conversation
    ) -> None:
        """Hand the turn to the bot, best-effort.

        The engine is resolved here rather than injected because it depends, transitively,
        on this package — an inbound message is what a bot turn *is*. Resolving at call
        time keeps that cycle out of the import graph.
        """
        from main.app.domain.channel.whatsapp.bot.engine import WhatsAppBotEngine

        try:
            await di[WhatsAppBotEngine].handle(message, conversation)
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(f"Bot failed to answer {message.from_phone}: {exc}")

    @staticmethod
    def _media_kind_for(message: InboundWhatsAppMessage) -> Optional[InboundKind]:
        """What arrived, when it was not words (§26.6.3).

        Null for text and for a menu selection, because neither is media — and the console
        derives "unofficial, never evidence" from this field being set, so labelling a text
        message would claim the evidence rule applies to it.
        """
        if message.kind in (InboundKind.TEXT, InboundKind.INTERACTIVE):
            return None
        return message.kind

    @staticmethod
    def _body_for(message: InboundWhatsAppMessage) -> str:
        """What the console shows. Never empty — an empty bubble reads as a bug."""
        if message.text:
            return message.text
        if message.kind == InboundKind.TEXT:
            return _PLACEHOLDER_BY_KIND[InboundKind.UNSUPPORTED]
        return _PLACEHOLDER_BY_KIND.get(
            message.kind, _PLACEHOLDER_BY_KIND[InboundKind.UNSUPPORTED]
        )

    @staticmethod
    def _subject_for(message: InboundWhatsAppMessage) -> str:
        """Thread subject: the sender's WhatsApp profile name when Meta supplies one."""
        return f"WhatsApp · {message.sender_name}" if message.sender_name else "WhatsApp enquiry"
