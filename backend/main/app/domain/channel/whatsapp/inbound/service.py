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

**Recording comes first, answering second**, as three separately durable steps:

1. The raw message is **journalled** in its own committed write (`WhatsAppInboundJournal`).
   This is the one step whose failure answers Meta with a 5xx, so Meta redelivers:
   nothing was kept, so a retry can't duplicate.
2. It is **surfaced** in the console under a row claim (`FOR UPDATE SKIP LOCKED`), in a
   savepoint. A failure here leaves the journal row unprocessed. The number's next message
   catches it up first (which works on serverless), and the sweep is the backstop.
3. It is **answered**: queued agent replies are flushed and the bot takes the turn, each in a
   savepoint. A failure costs a reply, never the message.

After step 1, failures are logged rather than raised. The webhook keeps acknowledging,
because sustained non-2xx answers get the subscription throttled and eventually disabled.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from datetime import timedelta
from typing import Awaitable, Callable, Dict, Tuple, TypeVar

from kink import di, inject

from main.app.domain.channel.whatsapp.inbound.models import (
    CreateWhatsAppInboundMessageDto,
    WhatsAppInboundMessage,
)
from main.app.domain.channel.whatsapp.inbound.journal import WhatsAppInboundJournal
from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.app.domain.communication.chat_message.models import MessageSource, SenderKind
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import AppodusBaseException
from main.appodus_utils.integrations.messaging.providers.whatsapp.attribution import (
    extract_page_code,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    INBOUND_NOT_JOURNALLED_CODE,
    InboundKind,
    InboundWhatsAppMessage,
)

logger: Logger = di["logger"]

T = TypeVar("T")

# A journalled message not surfaced within this long is presumed failed, not in flight.
_STALE_AFTER = timedelta(minutes=2)
_STALE_SWEEP_BATCH = 50


class InboundNotJournalledException(AppodusBaseException):
    """The message could not be journalled, so nothing of it was kept: Meta must redeliver."""

    def __init__(self, wamid: str):
        super().__init__(
            message=f"Inbound WhatsApp message {wamid} was not journalled",
            status_code=503,
            code=INBOUND_NOT_JOURNALLED_CODE,
        )

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
        whatsapp_link_service: WhatsAppLinkService,
        participant_service: ConversationParticipantService,
        whatsapp_inbound_journal: WhatsAppInboundJournal,
    ):
        self._journal = whatsapp_inbound_journal
        self._whatsapp_inbound_message_repo = whatsapp_inbound_message_repo
        self._conversations = conversation_service
        self._chat = chat_message_service
        self._whatsapp_link_service = whatsapp_link_service
        self._participants = participant_service

    async def ingest(self, message: InboundWhatsAppMessage) -> Optional[WhatsAppInboundMessage]:
        """Journal an inbound message, show it in the admin console, and answer it.

        Returns the journal row, or ``None`` when this delivery was already handled (a Meta
        redelivery), is being handled by a concurrent request, or could not be surfaced yet
        (it stays journalled for a later attempt). Raises `InboundNotJournalledException`
        only when the message could not be journalled at all.
        """
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

        try:
            await self._journal.record(CreateWhatsAppInboundMessageDto(
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
            ))
        except Exception as exc:
            raise InboundNotJournalledException(message.wamid) from exc

        # Earlier messages from this number that never reached the console come first, so
        # the thread keeps the order the customer wrote in.
        surfaced = await self._surface_pending(message.from_phone)
        current = surfaced.get(message.wamid)
        if current is None:
            return None

        record, conversation = current
        await self._best_effort(
            f"flushing queued replies on {conversation.id}",
            lambda: self._flush_queued_replies(conversation),
        )
        await self._best_effort(
            f"answering {record.id}", lambda: self._answer(message, conversation),
        )
        return record

    async def reprocess_stale(self) -> int:
        """Surface journalled messages whose first attempt failed; the count surfaced.

        The backstop behind the number's next message, for a customer who never writes again.
        """
        phones = await self._whatsapp_inbound_message_repo.phones_with_stale_unprocessed(
            Utils.datetime_now() - _STALE_AFTER, _STALE_SWEEP_BATCH,
        )
        surfaced = 0
        for phone in phones:
            surfaced += len(await self._surface_pending(phone))
        return surfaced

    async def _surface_pending(
        self, from_phone: str,
    ) -> Dict[str, Tuple[WhatsAppInboundMessage, Conversation]]:
        """Claim this number's unsurfaced messages and show each in the console.

        Each message is surfaced in its own savepoint, so one that fails stays journalled
        for a later attempt without undoing the others. Returns what was surfaced, by wamid.
        """
        surfaced: Dict[str, Tuple[WhatsAppInboundMessage, Conversation]] = {}
        for row in await self._whatsapp_inbound_message_repo.claim_unprocessed(from_phone):
            conversation = await self._best_effort(
                f"surfacing {row.id}", lambda row=row: self._surface(row),
            )
            if conversation is not None:
                surfaced[str(row.wamid)] = (row, conversation)
        return surfaced

    async def _surface(self, row: WhatsAppInboundMessage) -> Conversation:
        """Post one journalled message into its WhatsApp thread and mark it processed."""
        message = self._message_from_row(row)
        # The number's owner, through the channel's single identity lookup. It only matters
        # when this message opens the thread: a customer who linked on the website before
        # ever writing gets a thread created owned and visible to them, not orphaned.
        owner_id = await self._whatsapp_link_service.resolve_user_for_phone(message.from_phone)
        conversation = await self._conversations.get_or_create_whatsapp_thread(
            message.from_phone, user_id=owner_id, subject=self._subject_for(message)
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

        # The audit trail from a console message back to exactly what Meta delivered.
        row.chat_message_id = Utils.uuid_to_hex(chat_message.id)
        row.processed_at = Utils.datetime_now()
        self._whatsapp_inbound_message_repo._session.add(row)

        if owner_id:
            # Writing back means they have seen the thread — the fallback for customers
            # whose WhatsApp read receipts are off (D92), so the portal badge still clears.
            await self._participants.advance_read(
                conversation.id, owner_id, chat_message.delivered_at or chat_message.date_created
            )
        return conversation

    @staticmethod
    async def _best_effort(what: str, action: Callable[[], Awaitable[T]]) -> Optional[T]:
        """Run *action* in a savepoint; on failure roll back only it, log, and return None.

        The savepoint is what makes a caught failure harmless: an SQL error otherwise
        poisons the whole transaction, and the journal row's claim, the console message,
        and every other message in the batch would roll back with it. Ids are logged,
        never content — inbound bodies are customer PII.
        """
        try:
            async with get_db_session_from_context().begin_nested():
                return await action()
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(f"WhatsApp inbound: {what} failed: {type(exc).__name__}")
            return None

    @staticmethod
    def _message_from_row(row: WhatsAppInboundMessage) -> InboundWhatsAppMessage:
        """Rebuild the delivery from its journal row, which keeps everything surfacing needs."""
        return InboundWhatsAppMessage(
            wamid=row.wamid,
            from_phone=row.from_phone,
            kind=InboundKind(row.kind),
            text=row.text,
            page_code=row.page_code,
            interactive_id=row.interactive_id,
            media_id=row.media_id,
            media_mime_type=row.media_mime_type,
            sender_name=row.sender_name,
            received_at=row.received_at,
            raw=row.payload or {},
        )

    async def _flush_queued_replies(self, conversation: Conversation) -> None:
        """Send anything an agent typed while Meta's window was shut (§26.7, WA-41).

        This message just reopened the window, so the queue can go now. It runs **before**
        the bot turn deliberately: the agent's answer was written first and should arrive
        first, and a thread with a queued reply is sticky-`HUMAN` anyway (D57), so the bot
        will not be adding to it.

        Best-effort (`ingest` runs it in a savepoint) for the same reason ingestion's other
        side effects are — the inbound message is already journalled, and a failure here must
        not make Meta redeliver it.
        """
        from main.app.domain.channel.whatsapp.console_sender import WhatsAppConsoleSender

        await di[WhatsAppConsoleSender].flush(conversation)

    async def _answer(
        self, message: InboundWhatsAppMessage, conversation: Conversation
    ) -> None:
        """Hand the turn to the bot (best-effort: `ingest` runs it in a savepoint).

        The engine is resolved here rather than injected because it depends, transitively,
        on this package — an inbound message is what a bot turn *is*. Resolving at call
        time keeps that cycle out of the import graph.
        """
        from main.app.domain.channel.whatsapp.bot.surface import WhatsAppAssistantSurface

        await di[WhatsAppAssistantSurface].handle(message, conversation)

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
