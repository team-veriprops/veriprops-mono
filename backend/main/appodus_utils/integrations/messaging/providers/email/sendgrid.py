from decimal import Decimal
from typing import Dict, Any

from kink import inject
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils


@inject
class SendGridEmailProvider(IMessageProvider):

    def __init__(self):
        self.client = SendGridAPIClient(settings.SENDGRID_API_KEY)

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.SENDGRID_EMAIL

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        try:
            mail = Mail(
                from_email=settings.EMAIL_FROM_ADDRESS,
                to_emails=message.recipient,
                subject="Your Message Subject",  # Could be part of message model
                html_content=message.content
            )

            response = self.client.send(mail)

            message.sent_at = Utils.datetime_now()
            message.provider = self.name
            message.status = MessageStatus.SENT
            message.provider_id = response.headers["X-Message-Id"]
            return message

        except Exception as e:
            message.status = "failed"
            message.error = str(e)
            return message

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        # Implement webhook-based status tracking for better accuracy
        return {"status": "delivered"}  # Simplified for example
