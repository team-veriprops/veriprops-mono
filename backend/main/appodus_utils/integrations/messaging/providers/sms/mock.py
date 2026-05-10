from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils import Utils
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider

logger = di["logger"]

@inject
class MockSmsProvider(IMessageProvider):
    """Test/dev SMS provider — logs and suppresses. Never sends real SMS.

    Hard-fails with ValueError in production or staging — real SMS must never
    route through this provider. The routing rule already prevents that, but
    this guard is defence-in-depth (same pattern as SmtpEmailProvider).
    """

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.MOCK_SMS

    @property
    def supported_channels(self) -> List[MessageChannel]:
        return [MessageChannel.SMS]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        return {}

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        env = settings.ENVIRONMENT
        if env in {Environment.PRODUCTION, Environment.STAGING}:
            raise ValueError(
                "MockSmsProvider must not be used in production or staging. "
                f"Current environment: {env}"
            )

        recipient = message.to
        to_number = (
            recipient.recipient
            if isinstance(recipient.recipient, str)
            else ", ".join(recipient.recipient)
        )
        text = getattr(message.payload, "text", None) or ""

        logger.info(
            "[MockSmsProvider] SMS suppressed in %s. To: %s | Text: %.80s",
            env, to_number, text,
        )

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        return message
