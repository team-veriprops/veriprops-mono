import json
from decimal import Decimal
from typing import Dict, Any

from kink import inject
from pywebpush import webpush, WebPushException

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.exception.exceptions import NotImplementedException
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils


@inject
class WebPushProvider(IMessageProvider):
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        raise NotImplementedException("Feature don't apply")

    VAPID_CLAIMS = {
        "sub": f"mailto:{settings.WEB_PUSH_CONTACT_EMAIL}"
    }

    def __init__(self):
        self.vapid_private_key = settings.WEB_PUSH_PRIVATE_KEY
        self.vapid_public_key = settings.WEB_PUSH_PUBLIC_KEY

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.WEB_PUSH

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.PUSH]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        try:
            recipient = message.content["recipient"]
            payload = message.content["payload"]

            if recipient["platform"] != "web":
                message.status = "failed"
                message.error = "Invalid platform for web push"
                return message

            subscription_info = {
                "endpoint": recipient["web_push_subscription"]["endpoint"],
                "keys": recipient["web_push_subscription"]["keys"]
            }

            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.VAPID_CLAIMS
            )

            message.sent_at = Utils.datetime_now()
            message.provider = self.name
            message.status = MessageStatus.SENT
            return message

        except WebPushException as e:
            message.status = "failed"
            message.error = str(e)
            if e.response and e.response.status_code == 410:
                message.extras["subscription_expired"] = True
            return message
        except Exception as e:
            message.status = "failed"
            message.error = str(e)
            return message
