import re
from datetime import datetime
from typing import Optional, Dict, Any, Union

from pydantic import model_validator, Field, HttpUrl, ConfigDict
from sqlalchemy import (Column,
                        Index,
                        String,
                        Text,
                        Integer)

from main.appodus_utils import BaseEntity, InternalPageRequest, BaseQueryDto, Object
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT
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
    __table_args__ = (
        # Retry-sweep hot path: WHERE status = RETRYING AND next_retry_at <= now.
        Index("ix_messages_status_next_retry_at", "status", "next_retry_at"),
    )
    channel = Column(String(20), nullable=False)
    to = Column(JSONB_VARIANT, nullable=False)
    payload = Column(JSONB_VARIANT, nullable=False)
    status = Column(String(20), nullable=False, default=MessageStatus.PENDING)
    provider = Column(String(50))
    provider_id = Column(String(255))  # Provider's message ID
    error = Column(Text)
    retry_count = Column(Integer, default=0)   # retries attempted (0..threshold)
    priority = Column(Integer, default=MessagePriority.NORMAL)  # 1=high, 2=normal, 3=low
    scheduled_at = Column(UTCDateTime, nullable=True)
    next_retry_at = Column(UTCDateTime, nullable=True)  # when a RETRYING row re-dispatches
    expires_at = Column(UTCDateTime, nullable=True)  # retry horizon for time-bound content (OTP, reset links)
    sent_at = Column(UTCDateTime, nullable=True)
    delivered_at = Column(UTCDateTime, nullable=True)
    extras = Column(JSONB_VARIANT, default={})
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
    next_retry_at: Optional[datetime] = Field(None, description="When a RETRYING message becomes eligible for re-dispatch")
    expires_at: Optional[datetime] = Field(
        None, description="Retry horizon for time-bound content (e.g. OTP validity) — never re-dispatched past this")
    sent_at: Optional[datetime] = Field(None, description="Timestamp when the message was actually sent")
    delivered_at: Optional[datetime] = Field(None, description="Timestamp when the message was successfully delivered")
    extras: Dict[str, Any] = Field(default_factory=dict, description="Additional custom data or tracking metadata")
    callback_url: Optional[HttpUrl] = Field(None, description="Webhook URL for delivery status")
    sandbox_mode: Optional[bool] = False

    @model_validator(mode="after")
    def validate_object(self):
        self.validate_recipients(self)

        if isinstance(self.payload, WhatsappPayload):
            WhatsappPayload.validate_content(self.payload)

        return self

    @staticmethod
    def validate_recipients(obj: 'UpsertMessageDto') -> 'UpsertMessageDto':
        def normalize(val):
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        all_recipients = normalize(obj.to.recipient)
        cc_list = normalize(obj.to.cc_recipient)
        bcc_list = normalize(obj.to.bcc_recipient)

        total = len(all_recipients) + len(cc_list) + len(bcc_list)

        if obj.channel in {MessageChannel.SMS, MessageChannel.WHATSAPP} and total > 1:
            raise ValueError(f"{obj.channel.value.upper()} supports only one recipient")

        if total > 1000:
            raise ValueError("Total recipients must not exceed 1000")

        email_regex = r'^[^@]+@[^@]+\.[^@]+$'
        e164_regex = r'^\+[1-9]\d{1,14}$'
        wa_regex = r'^\d{1,15}$'

        for recipient in all_recipients + cc_list + bcc_list:
            if obj.channel == MessageChannel.EMAIL:
                if not re.fullmatch(email_regex, recipient):
                    raise ValueError(f"Invalid email address: {recipient}")
            elif obj.channel == MessageChannel.SMS:
                if not re.fullmatch(e164_regex, recipient):
                    raise ValueError(f"Invalid SMS number (E.164): {recipient}")
            elif obj.channel == MessageChannel.WHATSAPP:
                if not re.fullmatch(wa_regex, recipient):
                    raise ValueError(f"Invalid WhatsApp number: {recipient}")
            elif obj.channel in {MessageChannel.PUSH, MessageChannel.WEB_PUSH}:
                if not isinstance(recipient, str) or len(recipient) > 256:
                    raise ValueError(f"Invalid device token: {recipient}")

        if obj.channel != MessageChannel.EMAIL and (cc_list or bcc_list):
            raise ValueError("CC and BCC are only supported for email channel")

        return obj

    @classmethod
    def from_request(cls, request: MessageRequest) -> "UpsertMessageDto":
        """Convert a MessageRequest to UpsertMessageDto.

        MessageRequest and UpsertMessageDto share a compatible field set by design.
        Any schema change to either must be mirrored in the other. Two differences are
        reconciled explicitly:

        * the request's ``schedule_at`` is the DTO's ``scheduled_at`` (this model ignores
          unknown fields, so relying on the raw dump would silently drop the schedule);
        * the request's ``extras`` is optional while the DTO's is a required dict.
          ``model_dump`` emits an explicit ``None``, and pydantic applies a default only
          when a key is *absent* — so a request that simply never set ``extras`` failed
          validation. The builder always sets ``{}``, which is why this only bit a caller
          constructing ``MessageRequest`` directly (the bot's free-text replies), and it
          surfaced as a silently undelivered message rather than an error at the call site.
        """
        data = request.model_dump()
        data["scheduled_at"] = data.pop("schedule_at", None)
        if data.get("extras") is None:
            data.pop("extras", None)
        return cls(**data)

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


# Pydantic v2: Optional WITHOUT a default is a required field — the explicit
# ``= None`` defaults below are what make partial constructions
# (``_UpdateMessageDto(status=..., error=...)``) legal.
class _UpdateMessageDto(Object):
    status: Optional[MessageStatus] = None
    provider: Optional[MessageProviderName] = None
    provider_id: Optional[str] = None
    extras: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: Optional[int] = None
    priority: Optional[MessagePriority] = None
    next_retry_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class SearchMessageDto(InternalPageRequest, BaseQueryDto, _UpdateMessageDto):
    channel: Optional[MessageChannel] = None
    to: Optional[MessageRecipient] = None
    provider: Optional[MessageProviderName] = None


class QueryMessageDto(UpsertMessageDto, BaseQueryDto):
    pass
