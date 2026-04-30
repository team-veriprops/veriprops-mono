from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from typing import Any, Dict, List

from fastapi import BackgroundTasks
from kink import di

from main.app.config.settings import settings
from main.app.domain.message.message_payload_builder import MessageRecipientBuilder
# from main.app.domain.user.auth.active_auditor.service import ActiveAuditorService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.channel_sender import MessageDispatcher
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel, MultiChannelMessageRequest,
    MessageRequestRecipient, MessageCategory, MessageRecipientUserId, MessageContextModule, MessageContext
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

logger: Logger = di["logger"]

@decorate_all_methods(method_trace_logger, exclude=[''])
class BaseMessageSender:
    def __init__(self,
                 messaging_dispatcher: MessageDispatcher,
                 # active_auditor_service: ActiveAuditorService,
                 message_recipient_builder: MessageRecipientBuilder
                 ):
        self._messaging_dispatcher = messaging_dispatcher
        # self._active_auditor_service = active_auditor_service
        self._message_recipient_builder = message_recipient_builder

    async def _send_message(
            self,
            recipient_user_id: MessageRecipientUserId,
            template: AvailableTemplate,
            context_modules: List[MessageContextModule],
            category: MessageCategory,
            default_channels: List[MessageChannel],
            extra_context: Dict[str, Any] = None
    ) -> None:
        """Core method to handle all message sending logic."""
        recipient, template_context = await self._message_recipient_builder.build_recipient_and_context(
            recipient_user_id, context_modules
        )

        if extra_context:
            template_context.update(extra_context)

        await self._send_direct_message(
            recipient=recipient,
            template=template,
            context=template_context,
            category=category,
            default_channels=default_channels
        )

    async def _send_direct_message(self,
                                   recipient: MessageRequestRecipient,
                                   template: AvailableTemplate,
                                   context: Dict[str, Any],
                                   category: MessageCategory,
                                   default_channels: List[MessageChannel]):

        channels = self._get_available_channels(recipient, default_channels)
        if not channels:
            logger.info(f"Message send to '{recipient}', for '{template}' cannot continue: no available configured channel")
            return

        final_context = await self._build_context(
            context=context,
            category=category
        )

        request = MultiChannelMessageRequest(
            recipient=recipient,
            template=template,
            context=final_context,
            channels=channels
        )

        if settings.ENABLE_OUT_MESSAGING:
            # TODO: use BackgroundTasks
            # background_tasks: BackgroundTasks = await self._active_auditor_service.get_background_tasks_from_context()
            # # Fire-and-forget: the request returns immediately without waiting for delivery.
            # # Transient failures are retried by the router; fatal failures go to the DLQ.
            # # There is intentionally no delivery receipt at the call-site.
            # background_tasks.add_task(self._messaging_dispatcher.dispatch_to_channels, request)
            await self._messaging_dispatcher.dispatch_to_channels(request)
        else:
            cc = [r.email for r in recipient.cc_recipient]
            bcc = [r.email for r in recipient.bcc_recipient]
            logger.warning(
                f"Message dropped (ENABLE_OUT_MESSAGING=False): template='{template}', "
                f"channels={[c.value for c in channels]}, "
                f"recipient=(user_id={recipient.user_id}, fullname='{recipient.fullname}', "
                f"email={recipient.email.email if recipient.email else None}, "
                f"phone={recipient.phone.international_number if recipient.phone else None}, "
                f"ios_push_tokens={len(recipient.ios_push_token) if recipient.ios_push_token else 0}, "
                f"android_push_tokens={len(recipient.android_push_token) if recipient.android_push_token else 0}, "
                f"web_push_tokens={len(recipient.web_push_token) if recipient.web_push_token else 0}, "
                f"cc={cc}, bcc={bcc})"
            )

    @staticmethod
    def _get_available_channels(
            recipient: MessageRequestRecipient,
            default_channels: List[MessageChannel]
    ) -> List[MessageChannel]:
        """Filter default channels based on recipient's available contact methods."""
        channel_checks = {
            MessageChannel.EMAIL: bool(recipient.email),
            MessageChannel.SMS: bool(recipient.phone),
            MessageChannel.WHATSAPP: bool(recipient.phone),
            MessageChannel.PUSH: bool(recipient.ios_push_token or recipient.android_push_token),
            MessageChannel.WEB_PUSH: bool(recipient.web_push_token),
        }

        return [
            channel for channel in default_channels
            if channel_checks.get(channel, False)
        ]

    async def _build_context(
            self,
            context: Dict[str, Any],
            category: MessageCategory
    ) -> Dict[str, Any]:
        """Build the final context dictionary with defaults and overrides."""
        context = context.copy()

        context = await self._message_recipient_builder.build_global_context(context)

        context.update({
            MessageContext.CATEGORIES: [category]
        })
        return context
