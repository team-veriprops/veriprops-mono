import asyncio
import json
from decimal import Decimal
from logging import Logger
from typing import Any, Dict, List, Optional

from kink import inject, di
from pywebpush import webpush, WebPushException

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
    WebPushPayload,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils

logger: Logger = di['logger']

@inject
class WebPushProvider(IMessageProvider):
    """
    Browser Web Push provider using the VAPID protocol (pywebpush).
    Docs: https://web.dev/push-notifications-overview/
    The subscription info (endpoint + keys) is stored as a JSON string in message.to.recipient.
    Subscription format: {"endpoint": "...", "keys": {"auth": "...", "p256dh": "..."}}
    Uses pywebpush (sync) via asyncio.to_thread.
    """

    def __init__(self):
        self.vapid_private_key = settings.WEB_PUSH_PRIVATE_KEY
        self.vapid_claims = {"sub": f"mailto:{settings.WEB_PUSH_CONTACT_EMAIL}"}

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.WEB_PUSH

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.WEB_PUSH]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        recipient = message.to.recipient
        subscription_strings = recipient if isinstance(recipient, list) else [recipient]

        payload: WebPushPayload = message.payload
        data = self._build_notification(payload)
        serialised_data = json.dumps(data)

        success_count = 0
        last_error: Optional[str] = None

        for sub_str in subscription_strings:
            try:
                subscription_info = json.loads(sub_str)
            except (json.JSONDecodeError, TypeError):
                last_error = f"Invalid subscription JSON: {sub_str!r}"
                logger.warning("Skipping malformed web push subscription: {}", last_error)
                continue

            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info=subscription_info,
                    data=serialised_data,
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims=self.vapid_claims,
                )
                success_count += 1
            except WebPushException as e:
                if e.response is not None and e.response.status_code == 410:
                    last_error = "subscription expired (410 Gone)"
                elif e.response is not None and e.response.status_code == 401:
                    raise IntegrationException("Web push VAPID auth failed (401)")
                else:
                    last_error = str(e)
                logger.warning("Web push delivery failed for one subscription: {}", last_error)

        if success_count == 0:
            raise IntegrationException(
                f"Web push failed for all {len(subscription_strings)} subscription(s). "
                f"Last error: {last_error}"
            )

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = f"success:{success_count}/total:{len(subscription_strings)}"
        return message

    @staticmethod
    def _build_notification(payload: WebPushPayload) -> Dict[str, Any]:
        data: Dict[str, Any] = {"title": payload.title, "body": payload.body}
        if payload.icon_url:
            data["icon"] = str(payload.icon_url)
        if payload.image_url:
            data["image"] = str(payload.image_url)
        if payload.badge_url:
            data["badge"] = str(payload.badge_url)
        if payload.url:
            data["url"] = str(payload.url)
        if payload.actions:
            data["actions"] = [a.model_dump(mode="json") for a in payload.actions]
        if payload.vibrate:
            data["vibrate"] = payload.vibrate
        if payload.require_interaction:
            data["requireInteraction"] = payload.require_interaction
        if payload.silent:
            data["silent"] = payload.silent
        if payload.data:
            data["data"] = payload.data
        return data

    async def get_message_status(self, message_id: str) -> None:
        # Web push uses webhooks for delivery updates; polling is not supported.
        return None
