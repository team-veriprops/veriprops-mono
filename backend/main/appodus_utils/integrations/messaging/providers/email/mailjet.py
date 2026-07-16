from decimal import Decimal
from logging import Logger
from typing import Any, Dict, List

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
from main.appodus_utils.integrations.messaging.models import (
    Attachment,
    EmailPayload,
    MessageChannel,
    MessageProviderName,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils

logger: Logger = di['logger']

@inject
class MailjetEmailProvider(IMessageProvider):
    """
    Mailjet Send API v3.1.
    Docs: https://dev.mailjet.com/email/guides/send-api-v31/
    POST https://api.mailjet.com/v3.1/send
    Auth: HTTP Basic (api_key, api_secret)
    Success: 200 OK — message ID at Messages[0].To[0].MessageID (integer).
    Errors: 400 validation (Messages[0].Errors[].ErrorMessage), 401 auth, 429 rate-limit, 5xx server.
    """

    def __init__(self):
        self.api_key = settings.MAILJET_API_KEY
        self.api_secret = settings.MAILJET_API_SECRET
        self.client = di[AsyncClient]
        self.BASE_URL = settings.MAILJET_API

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.MAILJET

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        url = f"{self.BASE_URL}/v3.1/send"
        response = await self.client.post(
            url,
            json=self._build_body(message),
            auth=(self.api_key, self.api_secret),
        )

        if response.status_code == 401:
            raise IntegrationAuthenticationException("Invalid Mailjet API credentials")
        if response.status_code == 429:
            primary = message.to.recipient
            raise IntegrationRateLimitException(
                key=primary if isinstance(primary, str) else primary[0],
                reset_at=Utils.datetime_now_plus(minutes=1),
            )
        if 400 <= response.status_code < 500:
            errors = response.json().get("Messages", [{}])[0].get("Errors", [])
            detail = "; ".join(e.get("ErrorMessage", "") for e in errors) if errors else response.text
            raise IntegrationException(detail or "Mailjet API error")
        if response.status_code >= 500:
            response.raise_for_status()

        data = response.json()
        msg_result = data.get("Messages", [{}])[0]
        if msg_result.get("Status") != "success":
            raise IntegrationException(f"Mailjet rejected the message: {msg_result}")

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        to_list = msg_result.get("To", [{}])
        message.provider_id = str(to_list[0].get("MessageID", "")) if to_list else ""
        return message

    def _build_body(self, message: UpsertMessageDto) -> Dict[str, Any]:
        payload: EmailPayload = message.payload

        recipient = message.to.recipient
        to_list = (
            [{"Email": r} for r in recipient]
            if isinstance(recipient, list)
            else [{"Email": recipient, "Name": message.to.fullname}]
        )

        msg: Dict[str, Any] = {
            "From": {
                "Email": str(payload.from_email) if payload.from_email else settings.EMAIL_FROM_ADDRESS,
                "Name": payload.from_name or settings.EMAIL_FROM_NAME,
            },
            "To": to_list,
            "Subject": payload.subject,
            "CustomID": message.id or "",
        }

        if message.to.cc_recipient:
            msg["Cc"] = [{"Email": r.email, "Name": r.fullname} for r in message.to.cc_recipient]

        if message.to.bcc_recipient:
            msg["Bcc"] = [{"Email": r.email, "Name": r.fullname} for r in message.to.bcc_recipient]

        if payload.provider_template_id:
            msg["TemplateID"] = int(payload.provider_template_id)
            msg["TemplateLanguage"] = True
            msg["Variables"] = payload.provider_template_variables or {}
        else:
            if payload.html:
                msg["HTMLPart"] = payload.html
            if payload.text:
                msg["TextPart"] = payload.text

        if payload.attachments:
            msg["Attachments"] = self._build_attachments(payload.attachments)

        return {"Messages": [msg]}

    @staticmethod
    def _build_attachments(attachments: List[Attachment]) -> List[Dict[str, str]]:
        return [
            {
                "ContentType": att.content_type,
                "Filename": att.filename,
                "Base64Content": att.content,
            }
            for att in attachments
        ]

    async def get_message_status(self, message_id: str) -> str | None:
        # GET https://api.mailjet.com/v3/REST/messagehistory/{id}
        url = f"{self.BASE_URL}/v3/REST/messagehistory/{message_id}"
        try:
            response = await self.client.get(url, auth=(self.api_key, self.api_secret))
            response.raise_for_status()
            data = response.json().get("Data", [{}])
            return data[0].get("EventType") if data else None
        except Exception as e:
            logger.debug("Mailjet get_message_status failed for {}: {}", message_id, e)
            return None
