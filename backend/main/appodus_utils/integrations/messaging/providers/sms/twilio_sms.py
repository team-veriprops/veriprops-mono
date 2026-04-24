from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from kink import inject
from twilio.rest import Client

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager
from main.appodus_utils import Utils


@inject
class TwilioSMSProvider(IMessageProvider):
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.TWILIO_SMS

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.SMS]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        start_time = Utils.datetime_now()
        try:
            # Original send logic
            twilio_message = self.client.messages.create(
                body=message.content,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=message.recipient
            )

            duration = (Utils.datetime_now() - start_time).total_seconds()
            metrics_manager.track_message(
                channel="sms",
                provider=self.name,
                status="success",
                duration=duration
            )

            message.sent_at = Utils.datetime_now()
            message.status = MessageStatus.SENT
            message.provider = self.name
            message.provider_id = twilio_message.sid
            return message

        except Exception as e:
            duration = (Utils.datetime_now() - start_time).total_seconds()
            metrics_manager.track_message(
                channel="sms",
                provider=self.name,
                status="failed",
                duration=duration
            )
            metrics_manager.track_error(
                provider=self.name,
                error_type=e.__class__.__name__
            )
            raise

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        message = self.client.messages(message_id).fetch()
        return {
            "status": message.status,
            "date_sent": message.date_sent,
            "error_code": message.error_code
        }
