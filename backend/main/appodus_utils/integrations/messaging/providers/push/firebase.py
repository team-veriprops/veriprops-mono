from decimal import Decimal
from typing import Dict, Any

import firebase_admin
from firebase_admin import messaging
from kink import inject

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import PushNotificationProvider
from main.appodus_utils.integrations.messaging.providers.push.models import PushProviderType, PushNotificationRecipient, \
    PushNotificationPayload
from main.appodus_utils import Utils


@inject
class FirebasePushProvider(PushNotificationProvider):
    def __init__(self):
        if not firebase_admin._apps:
            cred = firebase_admin.credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.FIREBASE_PUSH

    @property
    def push_provider_type(self) -> PushProviderType:
        return PushProviderType.FIREBASE

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.PUSH]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_push(self, recipient: PushNotificationRecipient, payload: PushNotificationPayload) -> Dict[str, Any]:
        try:
            message = self._build_message(recipient, payload)

            if len(recipient.device_tokens) > 1:
                response = await messaging.send_multicast(message)
                return {"success_count": response.success_count, "failure_count": response.failure_count,
                        "responses": [str(r) for r in response.responses]}
            else:
                response = await messaging.send(message)
                return {"message_id": response}

        except Exception as e:
            raise IntegrationException(f"Firebase error: {str(e)}")

    def _build_message(self, recipient, payload):
        notification = messaging.Notification(title=payload.title, body=payload.body, image=payload.image_url)

        android_config = messaging.AndroidConfig(priority="high" if payload.priority == "high" else "normal",
                                                 ttl=payload.ttl)

        apns_config = messaging.APNSConfig(headers={"apns-priority": "10" if payload.priority == "high" else "5"},
                                           payload=messaging.APNSPayload(
                                               aps=messaging.Aps(
                                                   alert=messaging.ApsAlert(title=payload.title, body=payload.body),
                                                   sound="default")))

        return messaging.Message(notification=notification, data=payload.data or {},
                                 token=recipient.device_tokens[0] if len(recipient.device_tokens) == 1 else None,
                                 tokens=recipient.device_tokens if len(recipient.device_tokens) > 1 else None,
                                 android=android_config,
                                 apns=apns_config)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        """Implement base MessageProvider interface"""
        try:
            # Parse the message content as push notification
            payload_data = message.content.get("payload")
            recipient_data = message.content.get("recipient")

            payload = PushNotificationPayload(**payload_data)
            recipient = PushNotificationRecipient(**recipient_data)

            response = await self.send_push(recipient, payload)

            message.sent_at = Utils.datetime_now()
            message.provider = self.name
            message.status = MessageStatus.SENT
            message.provider_id = response.get("message_id", "")
            return message

        except Exception as e:
            message.status = "failed"
            message.error = str(e)
            return message

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        # Firebase doesn't provide message status checking via API
        return {"status": "unknown", "note": "Firebase doesn't support status checking"}
