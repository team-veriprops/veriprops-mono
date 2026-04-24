from decimal import Decimal
from typing import Dict, Any

from httpx import AsyncClient
from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationAuthenticationException, \
    IntegrationInsufficientBalanceException, IntegrationException, IntegrationRateLimitException
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils


@inject
class TermiiSMSProvider(IMessageProvider):
    """
    see API Doc here: https://developers.termii.com/messaging-api
    """

    def __init__(self):
        self.BASE_URL = settings.TERMII_API
        self.api_key = settings.TERMII_API_KEY
        self.client = di[AsyncClient]

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.TERMII_SMS

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.SMS]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        url = f"{self.BASE_URL}/sms/send"
        payload = {
            "to": message.to.recipient,
            "from": message.payload.sender_id,
            "sms": message.payload.text,
            "type": "plain",
            "channel": "generic",
            "api_key": self.api_key
        }

        response = await self.client.post(url, json=payload)

        if response.status_code == 401 or response.status_code == 403:
            raise IntegrationAuthenticationException("Invalid Termii API key")
        if response.status_code == 402:
            raise IntegrationInsufficientBalanceException("Insufficient Termii balance")
        if response.status_code == 429:
            raise IntegrationRateLimitException(key=message.recipient, reset_at=Utils.datetime_now_plus(minutes=5))
        if 400 <= response.status_code < 500:
            raise IntegrationException(response.text or "Termii API error")
        if response.status_code >= 500:
            response.raise_for_status()  # → httpx.HTTPStatusError → retried by resilience layer

        data = response.json()

        if data.get("code") != "ok":
            raise IntegrationException(data.get("message", "Termii rejected the message"))

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = data.get("message_id", "")
        return message

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/sms/{message_id}"
        params = {"api_key": self.api_key}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
