from decimal import Decimal
from typing import Dict, Any

import httpx
from httpx import AsyncClient
from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName, MessageStatus
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.providers.whatsapp.models import WhatsAppMessageType
from main.appodus_utils import Utils


@inject
class WhatsAppBusinessProvider(IMessageProvider):

    def __init__(self):
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.business_account_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID
        self.access_token = settings.WHATSAPP_BUSINESS_ACCESS_TOKEN
        self.client = di[AsyncClient]
        self.BASE_URL = settings.WHATSAPP_API_URL

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.WHATSAPP_BUSINESS

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.WHATSAPP]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            content = message.content
            message_type = content.get("message_type")

            if message_type == WhatsAppMessageType.TEXT:
                payload = self._build_text_payload(message)
            elif message_type == WhatsAppMessageType.TEMPLATE:
                payload = self._build_template_payload(message)
            elif message_type in [
                WhatsAppMessageType.IMAGE,
                WhatsAppMessageType.VIDEO,
                WhatsAppMessageType.AUDIO,
                WhatsAppMessageType.DOCUMENT
            ]:
                payload = self._build_media_payload(message)
            elif message_type == WhatsAppMessageType.INTERACTIVE:
                payload = self._build_interactive_payload(message)
            else:
                raise IntegrationException(f"Unsupported message type: {message_type}")

            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            message.sent_at = Utils.datetime_now()
            message.provider = self.name
            message.status = MessageStatus.SENT
            message.provider_id = data.get("messages", [{}])[0].get("id", "")
            return message

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            raise WhatsAppBusinessError(error_msg)
        except Exception as e:
            raise WhatsAppBusinessError(str(e))

    def _build_media_payload(self, message: UpsertMessageDto) -> Dict[str, Any]:
        content = message.content
        media_type = content["message_type"]
        media = content["media"]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.recipient,
            "type": media_type
        }

        if media.link:
            payload[media_type] = {
                "link": media.link,
                "caption": media.caption
            }
            if media_type == "document" and media.filename:
                payload[media_type]["filename"] = media.filename
        else:
            payload[media_type] = {
                "id": media.id,
                "caption": media.caption
            }

        return payload

    def _build_interactive_payload(self, message: UpsertMessageDto) -> Dict[str, Any]:
        content = message.content
        interactive = content["interactive"]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.recipient,
            "type": "interactive",
            "interactive": {
                "type": interactive.type,
                "body": interactive.body
            }
        }

        if interactive.header:
            payload["interactive"]["header"] = interactive.header

        if interactive.footer:
            payload["interactive"]["footer"] = interactive.footer

        if interactive.action.buttons:
            payload["interactive"]["action"] = {
                "buttons": [
                    {
                        "type": button.type,
                        button.type: {
                            "title": button.title,
                            "id" if button.type == "reply" else "link":
                                button.payload if button.type == "reply" else button.url
                        }
                    }
                    for button in interactive.action.buttons
                ]
            }
        elif interactive.action.sections:
            payload["interactive"]["action"] = {
                "button": interactive.action.button,
                "sections": [
                    {
                        "title": section.title,
                        "rows": [
                            {
                                "id": row.id,
                                "title": row.title,
                                "description": row.description
                            }
                            for row in section.rows
                        ]
                    }
                    for section in interactive.action.sections
                ]
            }

        return payload

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        # WhatsApp Business API doesn't provide direct status checking
        # Status updates come via webhooks
        return {"status": "unknown", "note": "Check via webhooks"}

    async def close(self):
        await self.client.aclose()
