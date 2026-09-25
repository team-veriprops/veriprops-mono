"""Meta's delivery and read receipts for what we sent (PRD §26.3.3, §26.8, D92).

Every outbound WhatsApp text — an agent's console reply or a bot reply — is stored with the
wamid Meta returned. A receipt citing that wamid:

* moves the message's ``channel_status`` forward, which the console shows as ticks;
* when it is a **read**, counts as the thread's owner reading the thread up to that message,
  so their portal unread badge clears without opening the website;
* updates the ``messages`` bookkeeping row for the same send.

Meta delivers receipts late, out of order and more than once, so every effect is
forward-only and a receipt for an unknown wamid is a no-op. Handling is best-effort from the
webhook's point of view: it logs and acknowledges whatever happens here.
"""
from __future__ import annotations

from logging import Logger

from kink import di, inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.communication.chat_message.models import (
    ChannelDeliveryStatus,
    ChatMessage,
    advance_channel_status,
)
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.conversation.models import Conversation, ConversationChannel
from main.app.domain.communication.conversation.repo import ConversationRepo
from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)
from main.app.domain.message.service import MessageService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundWhatsAppStatus,
    WhatsAppDeliveryStatus,
)

logger: Logger = di["logger"]

# Meta's lowercase receipt vocabulary → the status stored on the message.
_CHANNEL_STATUS_BY_RECEIPT = {
    WhatsAppDeliveryStatus.SENT: ChannelDeliveryStatus.SENT,
    WhatsAppDeliveryStatus.DELIVERED: ChannelDeliveryStatus.DELIVERED,
    WhatsAppDeliveryStatus.READ: ChannelDeliveryStatus.READ,
    WhatsAppDeliveryStatus.FAILED: ChannelDeliveryStatus.FAILED,
}

_ARRIVED = frozenset({ChannelDeliveryStatus.DELIVERED, ChannelDeliveryStatus.READ})


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppStatusService:
    def __init__(
        self,
        chat_message_repo: ChatMessageRepo,
        conversation_repo: ConversationRepo,
        participant_service: ConversationParticipantService,
        message_service: MessageService,
    ):
        self._chat_message_repo = chat_message_repo
        self._conversation_repo = conversation_repo
        self._participants = participant_service
        self._message_service = message_service

    async def apply(self, receipt: InboundWhatsAppStatus) -> bool:
        """Apply one receipt. Returns whether the message's delivery state moved."""
        new_status = _CHANNEL_STATUS_BY_RECEIPT[receipt.status]
        at = receipt.timestamp or Utils.datetime_now()
        await self._record_bookkeeping(receipt, new_status)

        message = await self._chat_message_repo.get_outbound_by_external_id(receipt.wamid)
        if message is None or not advance_channel_status(message.channel_status, new_status):
            return False

        message.channel_status = new_status.value
        message.channel_status_at = at
        self._chat_message_repo._session.add(message)

        conversation = await self._conversation_repo.get_model(message.conversation_id)
        if conversation is None:
            return True
        if new_status == ChannelDeliveryStatus.READ:
            await self._count_as_read(conversation, message)
        await self._nudge_members(conversation)
        return True

    async def _count_as_read(self, conversation: Conversation, message: ChatMessage) -> None:
        """A read on the phone reads the thread up to that message for its owner.

        Up to when the message reached the thread, not when the receipt came in: anything
        posted in the portal since has not been seen. An unlinked number has no owner, and
        ``advance_read`` refuses a closed window or a read that would move backwards.
        """
        if conversation.channel != ConversationChannel.WHATSAPP.value or not conversation.created_by:
            return
        await self._participants.advance_read(
            conversation.id, conversation.created_by, message.delivered_at or message.date_created
        )

    async def _nudge_members(self, conversation: Conversation) -> None:
        """Refresh the thread for everyone who can currently read it — the owner's badge and
        the ticks an admin who has the thread open is looking at."""
        members = await self._participants._participant_repo.list_for_conversation(conversation.id)
        await publish_domain_event(DomainEvent(
            type=EventType.MESSAGE_STATUS_CHANGED,
            recipient_user_ids=tuple(m.user_id for m in members if not m.is_read_only),
            data={"conversation_id": Utils.uuid_to_hex(conversation.id)},
        ))

    async def _record_bookkeeping(
        self, receipt: InboundWhatsAppStatus, status: ChannelDeliveryStatus
    ) -> None:
        """Mirror the receipt onto the ``messages`` row for the same send. Best-effort: the
        bookkeeping commits on its own, and a miss must not cost the console its ticks."""
        try:
            if status in _ARRIVED:
                await self._message_service.mark_delivered_by_provider_id(
                    receipt.wamid, receipt.timestamp or Utils.datetime_now()
                )
            elif status == ChannelDeliveryStatus.FAILED:
                codes = ", ".join(str(code) for code in receipt.error_codes) or "unknown"
                await self._message_service.mark_failed_by_provider_id(
                    receipt.wamid, f"WhatsApp delivery failed (Meta error {codes})"
                )
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.error(f"Could not record the receipt for {receipt.wamid}: {exc}")
