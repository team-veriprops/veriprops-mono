"""How an agent's console reply leaves the building (PRD §7.3.3, §7.7, WA-12/WA-41).

The outbound half of Decision K. Inbound WhatsApp already joins the ordinary conversation
pipeline and lands in the admin console; this is what carries a reply typed there back to
the customer's phone, so the console really is one console rather than a place where
messages arrive and stop.

Meta's 24-hour service window is the whole complication. Inside it we may send free text.
Outside it, the *only* thing Meta will deliver is an approved template — and `window_reopen`
carries no agent text, just "someone has replied, reply here to continue". So an agent
replying two days later gets:

* the nudge template sent now, and
* their own words **queued** on the message row (`channel_delivered_at` null) until the
  customer answers, which reopens the window and flushes the queue
  (`WhatsAppInboundService.ingest`).

Queueing rather than dropping matters because the thread is sticky-`HUMAN` by then (D57):
the bot will not answer the customer's "hi" either, so a dropped reply leaves them with a
nudge followed by silence — the §7.6.5 failure this channel exists to avoid.

**One nudge per closed-window episode.** An agent typing three messages must not send three
templates; the second and third simply join the queue behind the first.

Sending is best-effort and never raises. The message is already in the thread and the agent
has been told it sent; a raise would report a failure to the half of the system that
succeeded, and would roll back the console write that is our own record of what was said.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.app.domain.channel.whatsapp.window import WhatsAppWindowService
from main.app.domain.communication.chat_message.models import ChatMessage, SenderKind
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.conversation.models import Conversation, ConversationChannel
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageContext,
    MessageRecipient,
    MessageRequest,
    MessageRequestRecipient,
    WhatsappPayload,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_wa_recipient
from main.appodus_utils.integrations.messaging.service import MessagingService

logger: Logger = di["logger"]

# What `window_reopen` calls a customer we cannot name. A number with no linked account is
# the ordinary case for a §7.8 enquiry thread, and "Hello there" reads as intended where a
# blank or a raw phone number would read as broken.
ANONYMOUS_FIRST_NAME = "there"

# Only a person's reply travels back out. A SYSTEM message is either platform copy that
# lives in the console alone (a status breadcrumb) or a bot reply `bot/sender.py` already
# delivered — re-sending it would answer the customer twice.
_HUMAN_SENDERS = frozenset({SenderKind.ADMIN, SenderKind.AGENT})


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppConsoleSender:
    def __init__(
        self,
        messaging_service: MessagingService,
        whatsapp_window_service: WhatsAppWindowService,
        whatsapp_link_service: WhatsAppLinkService,
        chat_message_repo: ChatMessageRepo,
        user_repo: UserRepo,
    ):
        self._messaging_service = messaging_service
        self._whatsapp_window_service = whatsapp_window_service
        self._whatsapp_link_service = whatsapp_link_service
        self._chat_message_repo = chat_message_repo
        self._user_repo = user_repo

    async def deliver(self, conversation: Conversation, message: ChatMessage) -> None:
        """Carry one console reply out to the customer, or queue it behind a nudge."""
        if not self._is_deliverable(conversation, message):
            return

        phone_e164 = str(conversation.external_ref)
        if await self._whatsapp_window_service.is_open(phone_e164):
            if await self._deliver_text(phone_e164, message.body):
                self._mark_delivered(message)
            return

        # Outside the window the reply stays queued. The nudge goes only if this is the
        # first message waiting — the queue read includes this message, so "first" means
        # nothing else is ahead of it.
        if not await self._has_earlier_queued(conversation, message):
            await self._send_window_reopen(phone_e164)

    async def flush(self, conversation: Conversation) -> None:
        """Send everything queued on this thread, oldest first (§7.7).

        Called when the customer's own message reopens the window. Order is preserved
        because the agent wrote these as a sequence; delivering them out of order would
        rewrite the conversation the console shows.
        """
        for queued in await self._chat_message_repo.list_pending_channel_delivery(
            conversation.id
        ):
            if await self._deliver_text(str(conversation.external_ref), queued.body):
                self._mark_delivered(queued)

    # ─── Guards ───────────────────────────────────────────────────

    @staticmethod
    def _is_deliverable(conversation: Conversation, message: ChatMessage) -> bool:
        if conversation.channel != ConversationChannel.WHATSAPP.value:
            return False
        if not conversation.external_ref:
            # A WhatsApp thread with no number is a data fault, not a delivery target.
            return False
        if SenderKind(message.sender_kind) not in _HUMAN_SENDERS:
            return False
        # Already sent — a re-entrant `_deliver_effects` (an approve after a send) must not
        # duplicate the message on the customer's phone.
        return message.channel_delivered_at is None

    async def _has_earlier_queued(
        self, conversation: Conversation, message: ChatMessage
    ) -> bool:
        queued = await self._chat_message_repo.list_pending_channel_delivery(conversation.id)
        return any(str(other.id) != str(message.id) for other in queued)

    # ─── Transport ────────────────────────────────────────────────

    async def _deliver_text(self, phone_e164: str, text: str) -> bool:
        """Free text inside the window. Returns whether it actually went out."""
        if not settings.ENABLE_OUT_MESSAGING:
            # Same posture as the rest of the messaging pipeline: the console already
            # holds the message, so a local run without outbound stays fully inspectable.
            # Not marked delivered — nothing left the building.
            logger.warning(
                "Console reply not dispatched (ENABLE_OUT_MESSAGING=False): "
                f"recipient={to_wa_recipient(phone_e164)}"
            )
            return False
        try:
            await self._messaging_service.send_message(
                MessageRequest(
                    channel=MessageChannel.WHATSAPP,
                    to=MessageRecipient(recipient=to_wa_recipient(phone_e164)),
                    payload=WhatsappPayload(text=text),
                )
            )
            return True
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(f"Console reply delivery failed for {to_wa_recipient(phone_e164)}: {exc}")
            return False

    async def _send_window_reopen(self, phone_e164: str) -> None:
        """The §7.7 nudge that invites the customer back so the window reopens."""
        if not settings.ENABLE_OUT_MESSAGING:
            logger.warning(
                "window_reopen not dispatched (ENABLE_OUT_MESSAGING=False): "
                f"recipient={to_wa_recipient(phone_e164)}"
            )
            return
        from main.app.domain.user.user_messages import AccountSecurityMessages

        try:
            await di[AccountSecurityMessages].send_whatsapp_window_reopen_message(
                recipient=MessageRequestRecipient(phone=PhoneNumber.from_e164(phone_e164)),
                context={
                    MessageContext.FIRST_NAME: await self._first_name_for(phone_e164),
                },
            )
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(f"window_reopen failed for {to_wa_recipient(phone_e164)}: {exc}")

    async def _first_name_for(self, phone_e164: str) -> str:
        """Who the template greets.

        Identity comes through `WhatsAppLinkService.resolve_user_for_phone` — the channel's
        single identity lookup (§7.4.3), never a direct read of `whatsapp_links` — and an
        unlinked number is greeted neutrally rather than not at all.
        """
        user_id: Optional[str] = await self._whatsapp_link_service.resolve_user_for_phone(
            phone_e164
        )
        if not user_id:
            return ANONYMOUS_FIRST_NAME
        user = await self._user_repo.get_model(user_id)
        return getattr(user, "first_name", None) or ANONYMOUS_FIRST_NAME

    # ─── Bookkeeping ──────────────────────────────────────────────

    def _mark_delivered(self, message: ChatMessage) -> None:
        """Stamp the row that is attached to this transaction's session.

        Set on the object rather than re-fetched by id: the caller created or loaded it in
        this same uncommitted transaction, where a re-fetch can return `None` and the
        stamping would silently do nothing.
        """
        message.channel_delivered_at = Utils.datetime_now()
        self._chat_message_repo._session.add(message)
