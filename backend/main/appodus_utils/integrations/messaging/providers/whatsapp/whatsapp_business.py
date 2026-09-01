from decimal import Decimal
from logging import Logger
from typing import Any, Dict

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
    MessageChannel,
    MessageProviderName,
    MessageStatus,
    WhatsappButton,
    WhatsappPayload,
    WhatsappSection,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.providers.whatsapp.outbound import assert_no_outbound_voice
from main.appodus_utils import Utils

logger: Logger = di['logger']

@inject
class WhatsAppBusinessProvider(IMessageProvider):
    """
    WhatsApp Business Cloud API (Meta Graph API v22.0).
    Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
    POST https://graph.facebook.com/v22.0/{phone_number_id}/messages
    Auth: Authorization: Bearer {access_token}
    Success: 200 OK — message ID at messages[0].id.
    Errors: 401/403 auth (error.code 190), 400 bad request, 429 rate-limit, 5xx server.
    """

    def __init__(self):
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
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
            "Content-Type": "application/json",
        }

        payload: WhatsappPayload = message.payload
        assert_no_outbound_voice(payload)
        body = self._build_body(message.to.recipient, payload)

        response = await self.client.post(url, json=body, headers=headers)

        if response.status_code in (401, 403):
            error = response.json().get("error", {})
            raise IntegrationAuthenticationException(
                f"WhatsApp auth error (code {error.get('code', '')}): {error.get('message', response.text)}"
            )
        if response.status_code == 429:
            raise IntegrationRateLimitException(
                key=message.to.recipient,
                reset_at=Utils.datetime_now_plus(minutes=1),
            )
        if 400 <= response.status_code < 500:
            error = response.json().get("error", {})
            raise IntegrationException(error.get("message", response.text) or "WhatsApp API error")
        if response.status_code >= 500:
            response.raise_for_status()

        data = response.json()
        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = data.get("messages", [{}])[0].get("id", "")
        return message

    def _build_body(self, recipient: str, payload: WhatsappPayload) -> Dict[str, Any]:
        base = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
        }

        if payload.template_name:
            return {**base, **self._build_template(payload)}
        if payload.buttons:
            return {**base, **self._build_interactive_buttons(payload)}
        if payload.sections:
            return {**base, **self._build_interactive_list(payload)}
        if payload.media_url:
            return {**base, **self._build_media(payload)}
        return {**base, **self._build_text(payload)}

    @staticmethod
    def _build_text(payload: WhatsappPayload) -> Dict[str, Any]:
        return {
            "type": "text",
            "text": {"preview_url": False, "body": payload.text or ""},
        }

    @staticmethod
    def _build_template(payload: WhatsappPayload) -> Dict[str, Any]:
        """Meta's template message body.

        Body parameters are **positional**, and the keys carrying those positions are
        strings. Sorting them as strings puts "10" before "2", which silently delivers a
        customer the right values in the wrong sentence once a template passes nine
        parameters — so the sort is numeric, falling back to string order for any key
        that is not a position.
        """
        components = []
        if payload.template_variables:
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": v}
                    for _, v in sorted(
                        payload.template_variables.items(),
                        key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0]),
                    )
                ],
            })
        return {
            "type": "template",
            "template": {
                "name": payload.template_name,
                "language": {"code": payload.language_code or "en"},
                "components": components,
            },
        }

    @staticmethod
    def _build_media(payload: WhatsappPayload) -> Dict[str, Any]:
        media_type = payload.media_type.value  # image/video/document/audio
        media_obj: Dict[str, Any] = {"link": str(payload.media_url)}
        if payload.caption and media_type != "audio":
            media_obj["caption"] = payload.caption
        if media_type == "document" and payload.filename:
            media_obj["filename"] = payload.filename
        return {"type": media_type, media_type: media_obj}

    @staticmethod
    def _build_interactive_buttons(payload: WhatsappPayload) -> Dict[str, Any]:
        def _button(btn: WhatsappButton) -> Dict[str, Any]:
            return {
                "type": "reply",
                "reply": {"id": btn.payload or btn.title, "title": btn.title},
            }

        interactive: Dict[str, Any] = {
            "type": "button",
            "body": {"text": payload.text or ""},
            "action": {"buttons": [_button(b) for b in payload.buttons]},
        }
        if payload.header:
            interactive["header"] = {"type": "text", "text": payload.header.get("text", "")}
        if payload.footer:
            interactive["footer"] = {"text": payload.footer}
        return {"type": "interactive", "interactive": interactive}

    @staticmethod
    def _build_interactive_list(payload: WhatsappPayload) -> Dict[str, Any]:
        def _section(sec: WhatsappSection) -> Dict[str, Any]:
            return {
                "title": sec.title,
                "rows": [
                    {"id": r.id, "title": r.title, **({"description": r.description} if r.description else {})}
                    for r in sec.rows
                ],
            }

        interactive: Dict[str, Any] = {
            "type": "list",
            "body": {"text": payload.text or ""},
            "action": {
                "button": "Select",
                "sections": [_section(s) for s in payload.sections],
            },
        }
        if payload.header:
            interactive["header"] = {"type": "text", "text": payload.header.get("text", "")}
        if payload.footer:
            interactive["footer"] = {"text": payload.footer}
        return {"type": "interactive", "interactive": interactive}

    async def get_message_status(self, message_id: str) -> None:
        # WhatsApp Cloud API does not support polling message status.
        # Delivery updates are pushed via webhooks configured on the business account.
        return None
