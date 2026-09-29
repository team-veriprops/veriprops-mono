from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Any, Dict, List

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils import Utils
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider

logger = di["logger"]


@inject
class QaSinkProvider(IMessageProvider):
    """Where staging's messages to QA fixtures go instead of a live provider (`qa_recipients.py`).

    It records the message as sent and sends nothing, so a `/dev/scenario` case on staging runs
    its real notification rules without texting or emailing whoever owns a fixture's address.
    Refuses production outright, where fixtures cannot exist.
    """

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.QA_SINK

    @property
    def supported_channels(self) -> List[MessageChannel]:
        return [MessageChannel.SMS, MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        return {}

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        if settings.ENVIRONMENT == Environment.PRODUCTION:
            raise ValueError("QaSinkProvider must not be used in production.")
        logger.info("QA sink: {} message to a fixture recorded, not sent", message.channel.value)
        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = f"qa-sink-{secrets.token_hex(8)}"
        return message
