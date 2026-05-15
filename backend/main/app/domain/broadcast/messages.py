"""BroadcastMessages — sends admin broadcast notifications — S55."""
from __future__ import annotations

from kink import inject

from main.app.domain.message.message_sender import BaseMessageSender
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    MessageCategory,
    MessageChannel,
    MessageContext,
    MessageContextModule,
    MessageRecipientUserId,
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


@inject
@decorate_all_methods(method_trace_logger, exclude=[""])
class BroadcastMessages(BaseMessageSender):
    """External messaging for admin broadcast events."""

    async def send_broadcast(
        self,
        recipient_user_id: str,
        subject: str,
        body_html: str,
    ) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.ADMIN_BROADCAST,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.BROADCAST,
            default_channels=[MessageChannel.EMAIL, MessageChannel.PUSH],
            extra_context={
                MessageContext.BROADCAST_SUBJECT.value: subject,
                MessageContext.BROADCAST_BODY_HTML.value: body_html,
            },
        )
