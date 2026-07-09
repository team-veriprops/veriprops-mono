import asyncio
from datetime import timedelta
from decimal import Decimal
from logging import Logger
from typing import List

import firebase_admin
from firebase_admin import messaging
from firebase_admin import exceptions as firebase_exceptions
from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
    PushPayload,
    PushPriority,
)
from main.appodus_utils.integrations.messaging.providers.models import PushNotificationProvider
from main.appodus_utils.integrations.messaging.providers.push.models import PushProviderType
from main.appodus_utils import Utils

logger: Logger = di['logger']



from pathlib import Path

print("Current file:", __file__)
print("Current cwd:", Path.cwd())

for p in Path("/vercel/path1").rglob("firebase-service-account.json"):
    print("Found:", p)

@inject
class FirebasePushProvider(PushNotificationProvider):
    """
    Firebase Cloud Messaging (FCM) push notification provider.
    Docs: https://firebase.google.com/docs/cloud-messaging
    Uses firebase-admin SDK (sync) via asyncio.to_thread.
    Single token: messaging.send() → returns message ID string.
    Multiple tokens: messaging.send_each_for_multicast() → BatchResponse.
    """

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

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        payload: PushPayload = message.payload
        token = message.to.recipient

        tokens: List[str] = token if isinstance(token, list) else [token]

        try:
            if len(tokens) == 1:
                fcm_message = self._build_message(tokens[0], payload)
                message_id = await asyncio.to_thread(messaging.send, fcm_message)
                message.provider_id = message_id
            else:
                multicast = self._build_multicast(tokens, payload)
                batch = await asyncio.to_thread(messaging.send_each_for_multicast, multicast)
                message.provider_id = f"success:{batch.success_count}/failure:{batch.failure_count}"
        except firebase_exceptions.FirebaseError as e:
            raise IntegrationException(f"Firebase FCM error: {str(e)}")

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        return message

    def _build_message(self, token: str, payload) -> messaging.Message:
        notification, android_config, apns_config = self._build_configs(payload)
        return messaging.Message(
            token=token,
            notification=notification,
            data={k: str(v) for k, v in (payload.data or {}).items()},
            android=android_config,
            apns=apns_config,
        )

    def _build_multicast(self, tokens: List[str], payload) -> messaging.MulticastMessage:
        notification, android_config, apns_config = self._build_configs(payload)
        return messaging.MulticastMessage(
            tokens=tokens,
            notification=notification,
            data={k: str(v) for k, v in (payload.data or {}).items()},
            android=android_config,
            apns=apns_config,
        )

    @staticmethod
    def _build_configs(payload):
        is_high = getattr(payload, "priority", None) in ("high", PushPriority.HIGH)
        image = str(payload.image_url) if getattr(payload, "image_url", None) else None

        notification = messaging.Notification(
            title=payload.title,
            body=payload.body,
            image=image,
        )
        ttl_seconds = getattr(payload, "ttl", None)
        android_config = messaging.AndroidConfig(
            priority="high" if is_high else "normal",
            ttl=timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None,
        )
        apns_config = messaging.APNSConfig(
            headers={"apns-priority": "10" if is_high else "5"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=payload.title, body=payload.body),
                    sound=getattr(payload, "sound", None) or "default",
                    badge=getattr(payload, "badge", None),
                )
            ),
        )
        return notification, android_config, apns_config

    async def get_message_status(self, message_id: str) -> None:
        # FCM does not expose a REST endpoint to poll individual message delivery status.
        return None
