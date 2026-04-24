from decimal import Decimal

import mailjet_rest
from typing import Dict, Any, List
import logging

from kink import inject, di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.messaging.models import MessageStatus, MessageProviderName, MessageChannel
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils import Utils

logger: logging.Logger = di['logger']


@inject
class MailjetEmailProvider(IMessageProvider):
    def __init__(self):
        self.client = mailjet_rest.Client(
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_API_SECRET),
            version='v3.1'
        )

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.MAILJET

    @property
    def supported_channels(self) -> List[str]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        """
        Send email through Mailjet API
        Supports:
        - Single and multiple recipients
        - HTML and text content
        - Attachments
        - Templates with variables
        """
        try:
            email_data = self._prepare_email_data(message)

            # Use appropriate Mailjet API endpoint
            if 'TemplateID' in email_data:
                result = await self._send_template_email(email_data)
            else:
                result = await self._send_regular_email(email_data)

            message.sent_at = Utils.datetime_now()
            message.provider = self.name
            message.status = MessageStatus.SENT
            message.provider_id = result.get('Messages', [{}])[0].get('To')[0].get('MessageID')
            return message

        except Exception as e:
            logger.error(f"Mailjet send failed: {str(e)}", exc_info=True)
            message.status = "failed"
            message.error = str(e)
            raise IntegrationException(f"Mailjet send failed: {str(e)}")

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Check email status through Mailjet API
        """
        try:
            result = self.client.messagehistory.get(id=message_id)
            return {
                'status': result.json().get('Data', [{}])[0].get('EventType'),
                'details': result.json()
            }
        except Exception as e:
            logger.error(f"Mailjet status check failed: {str(e)}")
            return {'status': 'unknown', 'error': str(e)}

    def _prepare_email_data(self, message: UpsertMessageDto) -> Dict:
        """
        Prepare Mailjet API payload from our standard message format
        """
        content = message.content
        recipients = self._parse_recipients(message.recipient)

        base_payload = {
            'Messages': [{
                'From': {
                    'Email': content.get('from_email') or settings.EMAIL_FROM_ADDRESS,
                    'Name': content.get('from_name') or settings.EMAIL_FROM_NAME
                },
                'To': recipients['to'],
                'Cc': recipients['cc'],
                'Bcc': recipients['bcc'],
                'Subject': content.get('subject', 'No Subject'),
                'CustomID': message.id,
                'EventPayload': message.extras or {}
            }]
        }

        # Handle template vs regular email
        if 'template_id' in content:
            base_payload['Messages'][0]['TemplateID'] = content['template_id']
            base_payload['Messages'][0]['TemplateLanguage'] = True
            base_payload['Messages'][0]['Variables'] = content.get('variables', {})
        else:
            base_payload['Messages'][0]['HTMLPart'] = content.get('html')
            base_payload['Messages'][0]['TextPart'] = content.get('text')

        # Add attachments if present
        if 'attachments' in content:
            base_payload['Messages'][0]['Attachments'] = [
                {
                    'ContentType': att.get('content_type'),
                    'Filename': att.get('filename'),
                    'Base64Content': att.get('content')
                }
                for att in content['attachments']
            ]

        return base_payload

    def _parse_recipients(self, recipient_field: str) -> Dict:
        """
        Parse recipient string into Mailjet format
        Format: "to@example.com,cc@example.com,bcc@example.com"
        """
        parts = [p.strip() for p in recipient_field.split(',')]
        return {
            'to': [{'Email': parts[0]}],
            'cc': [{'Email': e} for e in parts[1:] if not e.startswith('bcc:')],
            'bcc': [{'Email': e[4:]} for e in parts if e.startswith('bcc:')]
        }

    async def _send_regular_email(self, email_data: Dict) -> Dict:
        """Send regular email through Mailjet API"""
        result = self.client.send.create(data=email_data)
        if result.status_code != 200:
            raise IntegrationException(f"Mailjet API error: {result.json()}")
        return result.json()

    async def _send_template_email(self, email_data: Dict) -> Dict:
        """Send template email through Mailjet API"""
        result = self.client.send.create(data=email_data)
        if result.status_code != 200:
            raise IntegrationException(f"Mailjet template error: {result.json()}")
        return result.json()
