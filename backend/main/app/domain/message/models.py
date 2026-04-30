import re
from datetime import datetime
from typing import Optional, Dict, Any, Union

from pydantic import model_validator, Field, HttpUrl, ConfigDict
from sqlalchemy import (Column,
                        String,
                        Text,
                        Integer,
                        DateTime)
from sqlalchemy.dialects.postgresql import JSONB

from main.appodus_utils import BaseEntity, PageRequest, BaseQueryDto, Object
from main.appodus_utils.integrations.messaging.models import (MessageChannel,
                                                                     MessageStatus,
                                                                     MessagePriority,
                                                                     MessageProviderName,
                                                                     MessageRequest)
from main.appodus_utils.integrations.messaging.models import (MessageRecipient,
                                                                     EmailPayload,
                                                                     SmsPayload,
                                                                     WhatsappPayload,
                                                                     PushPayload,
                                                                     WebPushPayload)


class Message(BaseEntity):
    __tablename__ = 'messages'
    channel = Column(String(20), nullable=False)
    to = Column(JSONB, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default=MessageStatus.PENDING)
    provider = Column(String(50))
    provider_id = Column(String(255))  # Provider's message ID
    error = Column(Text)
    retry_count = Column(Integer, default=0)
    priority = Column(Integer, default=MessagePriority.NORMAL)  # 1=high, 2=normal, 3=low
    scheduled_at = Column(DateTime(), nullable=True)
    sent_at = Column(DateTime(), nullable=True)
    delivered_at = Column(DateTime(), nullable=True)
    extras = Column(JSONB, default={})
    callback_url = Column(String(100))


class MessageBaseDto(Object):
    pass


# class CreateMessageDto(MessageBaseDto):
#     channel: MessageChannel
#     to: str
#     payload: Dict
#     provider: str
#     status: MessageStatus
#
#
# class UpdateMessageDto(MessageBaseDto):
#     pass


class UpsertMessageDto(MessageBaseDto):
    id: Optional[str] = Field(None, description="Unique message identifier")
    channel: MessageChannel = Field(..., description="Communication channel type")
    to: MessageRecipient = Field(..., description="Recipient details")
    payload: Union[
        EmailPayload,
        SmsPayload,
        WhatsappPayload,
        PushPayload,
        WebPushPayload,
    ] = Field(..., description="Content to be sent")
    status: MessageStatus = Field(default=MessageStatus.PENDING, description="Current status of the message")
    provider: Optional[MessageProviderName] = Field(None, description="Message provider (e.g., Twilio, Mailjet)")
    provider_id: Optional[str] = Field(None, description="External ID returned by the provider")
    error: Optional[str] = Field(None, description="Last error message encountered, if any")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts made so far")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="Delivery priority level")
    scheduled_at: Optional[datetime] = Field(None, description="Time at which message is scheduled to be sent")
    sent_at: Optional[datetime] = Field(None, description="Timestamp when the message was actually sent")
    delivered_at: Optional[datetime] = Field(None, description="Timestamp when the message was successfully delivered")
    extras: Dict[str, Any] = Field(default_factory=dict, description="Additional custom data or tracking metadata")
    callback_url: Optional[HttpUrl] = Field(None, description="Webhook URL for delivery status")
    sandbox_mode: Optional[bool] = False

    @model_validator(mode="after")
    def validate_recipients(self) -> 'UpsertMessageDto':
        def normalize(val):
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        all_recipients = normalize(self.to.recipient)
        cc_list = normalize(self.to.cc_recipient)
        bcc_list = normalize(self.to.bcc_recipient)

        total = len(all_recipients) + len(cc_list) + len(bcc_list)

        if self.channel in {MessageChannel.SMS, MessageChannel.WHATSAPP} and total > 1:
            raise ValueError(f"{self.channel.value.upper()} supports only one recipient")

        if total > 1000:
            raise ValueError("Total recipients must not exceed 1000")

        email_regex = r'^[^@]+@[^@]+\.[^@]+$'
        e164_regex = r'^\+[1-9]\d{1,14}$'
        wa_regex = r'^\d{1,15}$'

        for recipient in all_recipients + cc_list + bcc_list:
            if self.channel == MessageChannel.EMAIL:
                if not re.fullmatch(email_regex, recipient):
                    raise ValueError(f"Invalid email address: {recipient}")
            elif self.channel == MessageChannel.SMS:
                if not re.fullmatch(e164_regex, recipient):
                    raise ValueError(f"Invalid SMS number (E.164): {recipient}")
            elif self.channel == MessageChannel.WHATSAPP:
                if not re.fullmatch(wa_regex, recipient):
                    raise ValueError(f"Invalid WhatsApp number: {recipient}")
            elif self.channel in {MessageChannel.PUSH, MessageChannel.WEB_PUSH}:
                if not isinstance(recipient, str) or len(recipient) > 256:
                    raise ValueError(f"Invalid device token: {recipient}")

        if self.channel != MessageChannel.EMAIL and (cc_list or bcc_list):
            raise ValueError("CC and BCC are only supported for email channel")

        return self

    @classmethod
    def from_request(cls, request: MessageRequest) -> "UpsertMessageDto":
        """Convert a MessageRequest to UpsertMessageDto.

        MessageRequest and UpsertMessageDto share a compatible field set by design.
        Any schema change to either must be mirrored in the other.
        """
        return cls(**request.model_dump())

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        },
        json_schema_extra={
            "example": {
                "id": "msg_123",
                "channel": "email",
                "to": {
                    "recipient": "user@example.com",
                    "cc_recipient": ["cc@example.com"],
                    "bcc_recipient": ["bcc@example.com"]
                },
                "payload": {
                    "subject": "Welcome!",
                    "body": "<h1>Welcome</h1><p>Thank you for joining</p>"
                },
                "status": "pending",
                "priority": "normal",
                "extras": {
                    "campaign": "welcome_flow"
                }
            }
        }
    )


class _UpdateMessageDto(Object):
    status: Optional[MessageStatus]
    provider: Optional[MessageProviderName]
    provider_id: Optional[str]
    extras: Optional[Dict]
    error: Optional[str]
    retry_count: Optional[int]
    priority: Optional[MessagePriority]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]


class SearchMessageDto(PageRequest, BaseQueryDto, _UpdateMessageDto):
    channel: Optional[MessageChannel]
    to: Optional[MessageRecipient]
    provider: Optional[MessageProviderName]


class QueryMessageDto(UpsertMessageDto, BaseQueryDto):
    pass
