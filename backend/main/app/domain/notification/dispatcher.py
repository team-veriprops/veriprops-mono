"""External (email/SMS) fan-out for notifications (PRD §12.1).

A thin ``BaseMessageSender`` with one generic ``dispatch`` that sends a template on a
computed channel set — so the §4.8 rule table + per-user preferences decide the channels,
rather than each event hard-coding them. Reuses the existing messaging integration
(templates, providers, `ENABLE_OUT_MESSAGING` gate).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from kink import inject

from main.app.domain.message.message_sender import BaseMessageSender
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    MessageCategory,
    MessageChannel,
    MessageContextModule,
    MessageRecipientUserId,
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


@inject
@decorate_all_methods(method_trace_logger, exclude=[""])
class NotificationDispatcher(BaseMessageSender):
    """Sends a notification template to one user on a specific channel set."""

    async def dispatch(
        self,
        recipient_user_id: str,
        template: AvailableTemplate,
        channels: List[MessageChannel],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not channels:
            return
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=template,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTIONAL,
            default_channels=channels,
            extra_context=extra_context or None,
        )
