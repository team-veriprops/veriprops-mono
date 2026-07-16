from decimal import Decimal
from logging import Logger

from httpx import AsyncClient
from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationAuthenticationException,
    IntegrationException,
    IntegrationRateLimitException,
)
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils

logger: Logger = di['logger']

@inject
class TwilioSMSProvider(IMessageProvider):
    """
    Twilio Programmable SMS API.
    Docs: https://www.twilio.com/docs/sms/api/message-resource
    POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
    Auth: HTTP Basic (AccountSid, AuthToken)
    Request: form-encoded (To, From, Body)
    Success: 201 Created — message SID in response JSON sid field.
    Errors: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 429 Too Many Requests.
    """

    BASE_URL = "https://api.twilio.com/2010-04-01"

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.client = di[AsyncClient]

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.TWILIO_SMS

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.SMS]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        url = f"{self.BASE_URL}/Accounts/{self.account_sid}/Messages.json"
        data = {
            "To": message.to.recipient,
            "From": message.payload.sender_id or self.from_number,
            "Body": message.payload.text,
        }

        response = await self.client.post(
            url,
            data=data,
            auth=(self.account_sid, self.auth_token),
        )

        if response.status_code == 401:
            raise IntegrationAuthenticationException("Invalid Twilio credentials")
        if response.status_code == 403:
            raise IntegrationAuthenticationException(
                f"Twilio request forbidden: {response.json().get('message', response.text)}"
            )
        if response.status_code == 429:
            raise IntegrationRateLimitException(
                key=message.to.recipient,
                reset_at=Utils.datetime_now_plus(minutes=1),
            )
        if 400 <= response.status_code < 500:
            raise IntegrationException(
                response.json().get("message", response.text) or "Twilio API error"
            )
        if response.status_code >= 500:
            response.raise_for_status()

        data = response.json()
        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = data.get("sid", "")
        return message

    async def get_message_status(self, message_id: str) -> str | None:
        url = f"{self.BASE_URL}/Accounts/{self.account_sid}/Messages/{message_id}.json"
        try:
            response = await self.client.get(url, auth=(self.account_sid, self.auth_token))
            response.raise_for_status()
            return response.json().get("status")
        except Exception as e:
            logger.debug("Twilio get_message_status failed for %s: %s", message_id, e)
            return None
