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
class ResendEmailProvider(IMessageProvider):
    """
    Resend email API.
    Docs: https://resend.com/docs/api-reference/emails/send-email
    POST https://api.resend.com/emails
    Auth: Bearer token (API key)
    Success: 200 OK — message id at response body's "id".
    Errors: 401/403 auth, 422 validation, 429 rate-limit (retry-after header in seconds), 5xx server.
    """

    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.client = di[AsyncClient]
        self.BASE_URL = settings.RESEND_API

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.RESEND

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        url = f"{self.BASE_URL}/emails"
        response = await self.client.post(
            url,
            json=self._build_body(message),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

        if response.status_code in (401, 403):
            raise IntegrationAuthenticationException("Invalid Resend API credentials")
        if response.status_code == 429:
            primary = message.to.recipient
            retry_after = response.headers.get("retry-after")
            reset_at = (
                Utils.datetime_now_plus(seconds=int(retry_after))
                if retry_after and retry_after.isdigit()
                else Utils.datetime_now_plus(minutes=1)
            )
            raise IntegrationRateLimitException(
                key=primary if isinstance(primary, str) else primary[0],
                reset_at=reset_at,
            )
        if 400 <= response.status_code < 500:
            detail = response.json().get("message", "") if response.text else ""
            raise IntegrationException(detail or "Resend API error")
        if response.status_code >= 500:
            response.raise_for_status()

        data = response.json()
        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = data.get("id", "")
        return message

    def _build_body(self, message: UpsertMessageDto) -> Dict[str, Any]:
        payload: EmailPayload = message.payload

        recipient = message.to.recipient
        to_list = recipient if isinstance(recipient, list) else [recipient]

        from_email = str(payload.from_email) if payload.from_email else settings.EMAIL_FROM_ADDRESS
        from_name = payload.from_name or settings.EMAIL_FROM_NAME

        body: Dict[str, Any] = {
            "from": f"{from_name} <{from_email}>",
            "to": to_list,
            "subject": payload.subject,
        }

        if message.to.cc_recipient:
            body["cc"] = [r.email for r in message.to.cc_recipient]

        if message.to.bcc_recipient:
            body["bcc"] = [r.email for r in message.to.bcc_recipient]

        if payload.reply_to:
            body["reply_to"] = str(payload.reply_to)

        if payload.html:
            body["html"] = payload.html
        if payload.text:
            body["text"] = payload.text

        if payload.headers:
            body["headers"] = payload.headers

        if payload.categories:
            body["tags"] = [{"name": c, "value": c} for c in payload.categories]

        if payload.attachments:
            body["attachments"] = self._build_attachments(payload.attachments)

        return body

    @staticmethod
    def _build_attachments(attachments: List[Attachment]) -> List[Dict[str, str]]:
        result = []
        for att in attachments:
            entry: Dict[str, str] = {
                "filename": att.filename,
                "content": att.content,
                "content_type": att.content_type,
            }
            if att.content_id:
                entry["content_id"] = att.content_id
            result.append(entry)
        return result

    async def get_message_status(self, message_id: str) -> str | None:
        url = f"{self.BASE_URL}/emails/{message_id}"
        try:
            response = await self.client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
            response.raise_for_status()
            return response.json().get("last_event")
        except Exception as e:
            logger.debug("Resend get_message_status failed for {}: {}", message_id, e)
            return None
