import asyncio
import base64
import json
from decimal import Decimal
from logging import Logger
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
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
class AmazonSESEmailProvider(IMessageProvider):
    """
    Amazon SES v2 email provider.
    Docs: https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_SendEmail.html
    Uses boto3 sesv2 client (sync) via asyncio.to_thread.
    Auth: AWS credentials via settings (access key + secret).
    Success: 200 OK — MessageId in response body.
    Errors: ClientError with codes AccountSuspendedException, BadRequestException,
            MailFromDomainNotVerifiedException, MessageRejected, TooManyRequestsException, etc.
    """

    def __init__(self):
        self.ses = boto3.client(
            "sesv2",
            region_name=settings.AWS_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.AWS_SES

    @property
    def supported_channels(self) -> list[MessageChannel]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        kwargs = self._build_kwargs(message)

        try:
            response = await asyncio.to_thread(self.ses.send_email, **kwargs)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            if code in ("InvalidClientTokenId", "AuthFailure", "InvalidSignatureException"):
                raise IntegrationAuthenticationException(f"AWS SES auth error: {msg}")
            if code == "TooManyRequestsException":
                primary = message.to.recipient
                raise IntegrationRateLimitException(
                    key=primary if isinstance(primary, str) else primary[0],
                    reset_at=Utils.datetime_now_plus(minutes=1),
                )
            raise IntegrationException(f"AWS SES error ({code}): {msg}")

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        message.provider_id = response.get("MessageId", "")
        return message

    def _build_kwargs(self, message: UpsertMessageDto) -> Dict[str, Any]:
        payload: EmailPayload = message.payload

        recipient = message.to.recipient
        to_list = recipient if isinstance(recipient, list) else [recipient]

        destination: Dict[str, Any] = {"ToAddresses": to_list}
        if message.to.cc_recipient:
            destination["CcAddresses"] = [r.email for r in message.to.cc_recipient]
        if message.to.bcc_recipient:
            destination["BccAddresses"] = [r.email for r in message.to.bcc_recipient]

        from_address = settings.EMAIL_FROM_ADDRESS
        if payload.from_email:
            from_address = str(payload.from_email)
        from_name = payload.from_name or settings.EMAIL_FROM_NAME
        formatted_from = f"{from_name} <{from_address}>"

        kwargs: Dict[str, Any] = {
            "FromEmailAddress": formatted_from,
            "Destination": destination,
        }

        if payload.reply_to:
            kwargs["ReplyToAddresses"] = [str(payload.reply_to)]

        if payload.provider_template_id:
            kwargs["Content"] = {
                "Template": {
                    "TemplateName": payload.provider_template_id,
                    "TemplateData": json.dumps(payload.provider_template_variables or {}),
                }
            }
        else:
            simple: Dict[str, Any] = {
                "Subject": {"Data": payload.subject, "Charset": "UTF-8"},
                "Body": {},
            }
            if payload.html:
                simple["Body"]["Html"] = {"Data": payload.html, "Charset": "UTF-8"}
            if payload.text:
                simple["Body"]["Text"] = {"Data": payload.text, "Charset": "UTF-8"}
            if payload.attachments:
                simple["Attachments"] = self._build_attachments(payload.attachments)
            if payload.headers:
                simple["Headers"] = [
                    {"Name": k, "Value": v} for k, v in payload.headers.items()
                ]
            kwargs["Content"] = {"Simple": simple}

        if payload.categories:
            kwargs["EmailTags"] = [{"Name": "category", "Value": c} for c in payload.categories]

        return kwargs

    @staticmethod
    def _build_attachments(attachments: List[Attachment]) -> List[Dict[str, Any]]:
        result = []
        for att in attachments:
            entry: Dict[str, Any] = {
                "FileName": att.filename,
                "ContentType": att.content_type,
                "RawContent": base64.b64decode(att.content),
                "ContentDisposition": "INLINE" if att.content_id else "ATTACHMENT",
            }
            if att.content_id:
                entry["ContentId"] = att.content_id
            result.append(entry)
        return result

    async def get_message_status(self, message_id: str) -> str | None:
        try:
            response = await asyncio.to_thread(self.ses.get_message_insights, MessageId=message_id)
            return response.get("SendingStatus")
        except ClientError as e:
            logger.debug("SES get_message_status failed for {}: %s", message_id, e.response["Error"]["Message"])
            return None
