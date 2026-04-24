import base64
import enum
import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from pydantic import Field, field_validator, model_validator, HttpUrl, EmailStr, ConfigDict

from main.appodus_utils import Object
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.integrations.exception.exceptions import IntegrationValidationException
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

class PushProviderType(str, Enum):
    FIREBASE = "firebase"
    APNS = "apns"  # Apple Push Notification Service
    WEB_PUSH = "web_push"

class MessageChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PUSH = "push"  # Mobile push
    WEB_PUSH = "web_push"  # Browser push

class MessageContextModule(str, enum.Enum):
    USER = "user"


class MessageCategory(str, enum.Enum):
    LISTING = "listing"
    ALERT = "alert"
    MESSAGE = "message"
    UPDATE = "update"
    REENGAGEMENT = "reengagement"
    LEAD = "lead"
    APPOINTMENT = "appointment"
    ANALYTICS = "analytics"
    REVIEW = "review"
    CONFIRMATION = "confirmation"
    OFFER = "offer"
    TRANSACTION = "transaction"
    REFERRAL = "referral"
    PRODUCT_IMPROVEMENT = "product_improvement"
    FEEDBACK = "feedback"
    MARKETING = "marketing"
    ONBOARDING = "onboarding"
    VERIFICATION = "verification"
    SECURITY = "security"
    ADMIN = "admin"
    REMINDER = "reminder"


class MessageProviderName(str, Enum):
    TERMII_SMS = "TERMII_SMS"
    WHATSAPP_BUSINESS = "WHATSAPP_BUSINESS"
    WEB_PUSH = "WEB_PUSH"
    FIREBASE_PUSH = "FIREBASE_PUSH"
    TWILIO_SMS = "TWILIO_SMS"
    SENDGRID_EMAIL = "SENDGRID_EMAIL"
    MAILJET = "MAILJET"


class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class MessagePriority(int, Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


class ProviderPriority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


class MessageTemplate(Object):
    id: str
    name: str
    channel: str
    content: str
    variables: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


# class MessageRequest(Object):
#     channel: str
#     recipient: str
#     template_name: str
#     context: Dict[str, Any]
#     priority: Optional[MessagePriority] = MessagePriority.NORMAL


# class MessageResponse(Object):
#     message_id: str
#     status: str
#     channel: str
#     provider: Optional[str]


class Stat(Object):
    success: int = 0
    failure: int = 0
    last_used: Optional[datetime] = None
    cost_per_unit: Decimal = Decimal(0.0)


class AttachmentRequest(Object):
    """
    Input model for specifying a file to be attached to an email.

    Attributes:
        file_path (Path): Path to the file on the filesystem.
        filename (str): Override the file's name in the email.
    """
    file_path: Path = Field(..., description="The full path of the attached file", examples=["tmp/document.pdf"])
    filename: str = Field(..., description="Name of the attached file", examples=["document.pdf"])

    @field_validator('file_path')
    @classmethod
    def check_file_exists(cls, value: Path):
        """Ensure the file exists before processing."""
        if not value.exists():
            raise IntegrationValidationException(f"File not found: {value}")
        return value


class Attachment(Object):
    content_type: str = Field(
        default="application/octet-stream",
        description="MIME type of the attachment",
        examples=["application/pdf", "image/png"]
    )
    filename: str = Field(..., description="Name of the attached file", examples=["document.pdf"])
    content: str = Field(..., description="Base64 encoded content of the attachment")
    content_id: Optional[str] = Field(None, description="For inline images in HTML email", examples=["<image1>"])

    @field_validator('content')
    @classmethod
    def validate_base64(cls, v):
        try:
            base64.b64decode(v, validate=True)
            return v
        except Exception:
            raise IntegrationValidationException("Invalid base64 content")


class EmailPayloadRequest(Object):
    """Complete email message payload"""
    subject: str = Field(..., max_length=998)
    html: Optional[str] = Field(
        None,
        description="HTML content (required if text not provided)",
        examples=["<h1>Welcome</h1><p>Thank you for joining!</p>"]
    )
    text: Optional[str] = Field(
        None,
        description="Plain text content (required if html not provided)",
        examples=["Welcome\nThank you for joining!"]
    )
    from_email: Optional[EmailStr] = Field(
        None,
        pattern=r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
        examples=["noreply@company.com"]
    )
    from_name: Optional[str] = Field(None, max_length=998, examples=["Company Support"])
    reply_to: Optional[EmailStr] = Field(
        None,
        pattern=r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
        examples=["support@company.com"]
    )
    attachments: Optional[List[AttachmentRequest]] = Field(default_factory=list)
    provider_template_id: Optional[str] = Field(
        None,
        description="ID for template services like Mailjet/SendGrid",
        examples=["welcome_template"]
    )
    provider_template_variables: Optional[Dict[str, str]] = Field(
        None,
        examples=[{"name": "John", "activation_link": "https://example.com/activate"}]
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        examples=[{"X-Custom-Header": "value"}]
    )
    categories: Optional[List[str]] = Field(
        None,
        examples=["welcome", "onboarding"]
    )
    send_at: Optional[datetime] = Field(
        None,
        description="Schedule email for future delivery"
    )

    # @model_validator(mode='after')
    # def validate_content(cls, values):
    #     has_content = values.html or values.text
    #     has_template = values.provider_template_id
    #
    #     if not has_content and not has_template:
    #         raise IntegrationValidationException("Email requires 'html', 'text', or 'provider_template_id'")
    #     if has_template and not values.provider_template_variables:
    #         raise IntegrationValidationException("'provider_template_variables' required when using 'provider_template_id'")
    #     return values


class EmailPayload(EmailPayloadRequest):
    attachments: Optional[List[Attachment]] = Field(default_factory=list)


class SmsPayload(Object):
    """Complete SMS message payload"""
    text: Optional[str] = Field(
        None,
        max_length=1600,
        description="Supports concatenated SMS (max 10 segments), it's optional since we can build 'text' from template",
        examples=["Your verification code is 123456"]
    )
    sender_id: Optional[str] = Field(
        None,
        max_length=11,
        pattern=r'^[a-zA-Z0-9 ]+$',
        description="Alphanumeric sender ID",
        examples=["veriprops"]
    )
    unicode: bool = Field(
        False,
        description="Set to true if message contains non-GSM characters"
    )
    flash: bool = Field(
        False,
        description="Flash SMS (appears directly on screen)"
    )
    ttl: Optional[int] = Field(
        None,
        ge=60,
        le=86400,
        description="Time-to-live in seconds (60-86400)"
    )


class WhatsappMediaType(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"
    STICKER = "sticker"


class WhatsappButtonType(str, Enum):
    REPLY = "reply"
    URL = "url"
    CALL = "call"
    QUICK_REPLY = "quick_reply"


class WhatsappButton(Object):
    """Interactive button for WhatsApp messages"""
    type: WhatsappButtonType
    title: str = Field(..., max_length=20)
    payload: Optional[str] = Field(
        None,
        max_length=256,
        description="Required for reply buttons"
    )
    url: Optional[HttpUrl] = Field(
        None,
        description="Required for URL buttons"
    )
    phone_number: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9]\d{1,14}$',
        description="Required for call buttons"
    )


class WhatsappSectionRow(Object):
    """Row in a WhatsApp list section"""
    id: str = Field(..., max_length=200)
    title: str = Field(..., max_length=24)
    description: Optional[str] = Field(None, max_length=72)


class WhatsappSection(Object):
    """Section in a WhatsApp interactive message"""
    title: str = Field(..., max_length=24)
    rows: List[WhatsappSectionRow] = Field(..., min_items=1, max_items=10)


class WhatsappPayload(Object):
    """Complete WhatsApp message payload"""
    text: Optional[str] = Field(
        None,
        max_length=4096,
        description="Required if no media/template provided"
    )
    media_url: Optional[HttpUrl] = Field(
        None,
        description="Publicly accessible media URL"
    )
    media_type: Optional[WhatsappMediaType] = Field(
        None,
        description="Required if media_url provided"
    )
    caption: Optional[str] = Field(None, max_length=1024)
    filename: Optional[str] = Field(
        None,
        description="For document messages",
        examples=["report.pdf"]
    )
    template_name: Optional[str] = Field(
        None,
        max_length=512,
        description="Official WhatsApp template name"
    )
    template_variables: Optional[Dict[str, str]] = Field(
        None,
        description="Variables for template messages"
    )
    language_code: str = Field(
        "en",
        pattern=r'^[a-z]{2}$',
        description="Two-letter language code",
        examples=["en"]
    )
    buttons: Optional[List[WhatsappButton]] = Field(
        None,
        description="For interactive messages",
        max_length=3
    )
    sections: Optional[List[WhatsappSection]] = Field(
        None,
        description="For list messages",
        max_length=10
    )
    header: Optional[Dict[str, str]] = Field(
        None,
        description="Header for interactive messages"
    )
    footer: Optional[str] = Field(
        None,
        max_length=60,
        description="Footer text"
    )
    has_local_template: Optional[bool] = Field(
        False,
        description="Whether a local template exists, I will be attached in the parent request"
    )

    @model_validator(mode='after')
    def validate_content(self):
        has_text = bool(self.text)
        has_media = bool(self.media_url)
        has_template = bool(self.template_name)
        has_interactive = bool(self.buttons) or bool(self.sections)

        if not (has_text or has_media or has_template or has_interactive or self.has_local_template):
            raise IntegrationValidationException(
                "WhatsApp message requires text, media, template, or interactive content")

        if has_media and not self.media_type:
            raise IntegrationValidationException("media_type is required when media_url is provided")

        if has_template and not self.template_variables:
            raise IntegrationValidationException("template_variables are required for templates")

        if self.buttons and self.sections:
            raise IntegrationValidationException("Cannot have both buttons and sections")

        return self


class PushPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class PushPayload(Object):
    """Complete push notification payload"""
    title: str = Field(..., max_length=100)
    body: str = Field(..., max_length=200)
    data: Optional[Dict[str, str]] = Field(
        None,
        examples=[{"action": "open_screen", "screen": "messages"}]
    )
    image_url: Optional[HttpUrl] = Field(
        None,
        description="URL of rich notification image"
    )
    action_url: Optional[HttpUrl] = Field(
        None,
        description="Deep link URL when notification clicked"
    )
    priority: PushPriority = Field(
        PushPriority.NORMAL,
        description="Delivery priority"
    )
    ttl: Optional[int] = Field(
        None,
        ge=0,
        le=2419200,
        description="Time-to-live in seconds (max 28 days)"
    )
    badge: Optional[int] = Field(
        None,
        ge=0,
        description="App icon badge count"
    )
    sound: Optional[str] = Field(
        None,
        description="Notification sound file",
        examples=["default"]
    )
    channel_id: Optional[str] = Field(
        None,
        description="Android notification channel ID",
        examples=["urgent_alerts"]
    )


class WebPushAction(Object):
    """Action button for web push notifications"""
    action: str = Field(..., max_length=50)
    title: str = Field(..., max_length=50)
    icon: Optional[HttpUrl] = Field(
        None,
        description="URL of action icon"
    )


class WebPushPayload(Object):
    """Complete web push notification payload"""
    title: str = Field(..., max_length=100)
    body: str = Field(..., max_length=200)
    icon_url: Optional[HttpUrl] = Field(
        None,
        description="URL of notification icon"
    )
    badge_url: Optional[HttpUrl] = Field(
        None,
        description="URL of badge icon"
    )
    image_url: Optional[HttpUrl] = Field(
        None,
        description="URL of large notification image"
    )
    url: Optional[HttpUrl] = Field(
        None,
        description="URL to open when notification clicked"
    )
    actions: Optional[List[WebPushAction]] = Field(
        None,
        max_length=2,
        description="Action buttons"
    )
    vibrate: Optional[List[int]] = Field(
        None,
        description="Vibration pattern in milliseconds",
        examples=[200, 100, 200]
    )
    require_interaction: bool = Field(
        False,
        description="Notification stays until dismissed"
    )
    silent: bool = Field(
        False,
        description="No sound or vibration"
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="When the event occurred"
    )
    data: Optional[Dict[str, str]] = Field(
        None,
        description="Custom payload data"
    )

class MessageRecipientUserId(Object):
    user_id: str
    cc_recipients: Optional[List[str]] = None
    bcc_recipients: Optional[List[str]] = None

class PushToken(Object):
    token: str = Field(..., description="Push token string")
    device_id: Optional[str] = Field(None, description="Optional device identifier")

class EmailRecipient(Object):
    email: str
    fullname: str

# class PhoneNumber(Object):
#     dial_code: str
#     number: str

# class PhoneNumber(Object):
#     dial_code: str
#     number: str
#
#     @property
#     def internation_number(self)-> str:
#         return f"{self.dial_code}{self.number}"
#
#     @field_validator('number', mode='before')
#     def normalize_number(cls, v: str) -> str:
#         if not v:
#             raise ValueError("Phone number cannot be empty")
#         # Remove non-digit characters
#         digits_only = ''.join(filter(lambda c: c.isdigit(), v))
#         # Remove leading zeros
#         normalized = digits_only.lstrip('0')
#         if not normalized:
#             raise ValueError("Phone number cannot be all zeros")
#         return normalized



class MessageRequestRecipient(Object):
    """ This represents a user recipient, with possible multiple channels"""

    user_id: Optional[str] = None
    fullname: str
    email: Optional[EmailRecipient] = None
    phone: Optional[PhoneNumber] = None
    ios_push_token: Optional[List[dict]] = None
    android_push_token: Optional[List[dict]] = None
    web_push_token: Optional[List[dict]] = None
    cc_recipient: Union[EmailRecipient, List[EmailRecipient]] = Field(
        default_factory=list,
        description="CC recipient(s). Only applicable for email channel."
    )
    bcc_recipient: Union[EmailRecipient, List[EmailRecipient]] = Field(
        default_factory=list,
        description="BCC recipient(s). Only applicable for email channel."
    )


class MultiChannelMessageRequest(Object):
    recipient: MessageRequestRecipient
    template: AvailableTemplate
    context: Dict[str, Any]
    channels: List[MessageChannel]

    @field_validator('channels')
    def validate_channels(cls, v):
        if not v:
            raise ValueError("At least one channel must be specified")
        return v


class MessageRecipient(Object):
    recipient: Union[str, List[str]] = Field(
        ...,
        description="Primary recipient(s). Format depends on the selected channel."
    )
    fullname: str = Field(..., description="Recipient's fullname; Firstname Lastname.")
    cc_recipient: Union[str, List[str]] = Field(
        default_factory=list,
        description="CC recipient(s). Only applicable for email channel."
    )
    bcc_recipient: Union[str, List[str]] = Field(
        default_factory=list,
        description="BCC recipient(s). Only applicable for email channel."
    )


class MessageRequestBuilder:
    """
    Builder class for constructing MessageRequest objects step-by-step.

    This implements the Builder pattern to provide a fluent interface for creating
    complex MessageRequest objects with many optional parameters.

    Usage:
        builder = MessageRequestBuilder()
        request = (builder
                  .channel(MessageChannel.EMAIL)
                  .to(MessageRecipient(recipient="user@example.com"))
                  .payload(EmailPayloadRequest(subject="Hello"))
                  .build()
                  )

    Or using the static constructor:
        request = (MessageRequest.builder()
                  .channel(...)
                  .to(...)
                  .build())

    Methods return the builder instance to enable method chaining.
    The build() method validates and returns the final MessageRequest object.
    """

    def __init__(self):
        """Initialize all fields with default values"""
        self._channel = None
        self._to = None
        self._priority = MessagePriority.NORMAL
        self._payload = None
        self._template = None
        self._template_variables = None
        self._schedule_at = None
        self._extras = None
        self._sandbox_mode = False

    def channel(self, channel: MessageChannel) -> 'MessageRequestBuilder':
        """Set the message channel (required)"""
        self._channel = channel
        return self

    def to(self, to: MessageRecipient) -> 'MessageRequestBuilder':
        """Set the message recipient(s) (required)"""
        self._to = to
        return self

    def priority(self, priority: MessagePriority) -> 'MessageRequestBuilder':
        """Set the message priority (default: NORMAL)"""
        self._priority = priority
        return self

    def payload(self, payload: Union[
        EmailPayloadRequest, SmsPayload, WhatsappPayload, PushPayload, WebPushPayload
    ]) -> 'MessageRequestBuilder':
        """Set the message payload (required)"""
        self._payload = payload
        return self

    def template(self, template: Optional[AvailableTemplate]) -> 'MessageRequestBuilder':
        """Set the template ID (optional)"""
        self._template = template
        return self

    def template_variables(self, template_variables: Optional[Dict[str, str]]) -> 'MessageRequestBuilder':
        """Set template variables (optional)"""
        self._template_variables = template_variables
        return self

    def schedule_at(self, schedule_at: Optional[datetime]) -> 'MessageRequestBuilder':
        """Set scheduled delivery time (optional)"""
        self._schedule_at = schedule_at
        return self

    def extras(self, extras: Optional[Dict[str, str]]) -> 'MessageRequestBuilder':
        """Set analytics/tracking data (optional)"""
        self._extras = extras
        return self

    def sandbox_mode(self, sandbox_mode: Optional[bool]) -> 'MessageRequestBuilder':
        """Enable/disable sandbox mode (default: False)"""
        self._sandbox_mode = sandbox_mode
        return self

    def build(self) -> 'MessageRequest':
        """
        Construct and validate the MessageRequest object.

        Returns:
            MessageRequest: The fully constructed message request

        Raises:
            ValueError: If required fields (channel, to, payload) are missing
            IntegrationValidationException: If recipient validation fails
        """
        if not all([self._channel, self._to, self._payload]):
            raise ValueError("channel, to, and payload are required fields")

        return MessageRequest(
            channel=self._channel,
            to=self._to,
            priority=self._priority,
            payload=self._payload,
            template=self._template,
            template_variables=self._template_variables,
            schedule_at=self._schedule_at,
            extras=self._extras,
            sandbox_mode=self._sandbox_mode
        )


class MessageRequest(Object):
    """
    Complete unified message request model.

    This represents a message that can be sent through various channels (email, SMS, etc).
    For construction, use the MessageRequestBuilder via the builder() static method.

    Example Usage:
        # Using builder pattern (recommended)
        request = (MessageRequest.builder()
                  .channel(MessageChannel.EMAIL)
                  .to(MessageRecipient(recipient="user@example.com"))
                  .payload(EmailPayloadRequest(subject="Hello"))
                  .build())

        # Traditional construction
        request = MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(...),
            payload=EmailPayloadRequest(...)
        )

    The builder pattern is preferred for better readability, especially with many optional fields.
    """
    channel: MessageChannel
    to: MessageRecipient = Field(
        ...,
        description="Recipient(s) - format depends on channel"
    )
    priority: MessagePriority = Field(
        MessagePriority.NORMAL,
        description="Message send priority"
    )
    payload: Union[
        EmailPayloadRequest,
        SmsPayload,
        WhatsappPayload,
        PushPayload,
        WebPushPayload,
    ]
    template: Optional[AvailableTemplate] = Field(
        None,
        description="ID for template services like Mailjet/SendGrid",
        examples=["welcome_template"]
    )
    template_variables: Optional[Dict[str, str]] = Field(
        None,
        examples=[{"name": "John", "activation_link": "https://example.com/activate"}]
    )
    schedule_at: Optional[datetime] = Field(
        None,
        description="Future delivery time"
    )
    extras: Optional[Dict[str, str]] = Field(
        None,
        description="Tracking and analytics data, etc",
        examples=[{"campaign_id": "summer_sale", "user_id": "123"}]
    )
    sandbox_mode: Optional[bool] = False

    @model_validator(mode="after")
    def validate_recipients(self) -> 'MessageRequest':
        """Validate recipients based on channel rules"""

        def normalize(val):
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        all_recipients = normalize(self.to.recipient) + normalize(self.to.cc_recipient) + normalize(
            self.to.bcc_recipient)
        count = len(all_recipients)

        if self.channel in {MessageChannel.SMS, MessageChannel.WHATSAPP} and count > 1:
            raise IntegrationValidationException(f"{self.channel.value.upper()} only supports a single recipient")

        if count > 1000:
            raise IntegrationValidationException("Max 1000 recipients allowed across all fields")

        for r in all_recipients:
            if self.channel == MessageChannel.SMS:
                if not re.fullmatch(r'^\+[1-9]\d{1,14}$', r):
                    raise IntegrationValidationException(f"Invalid SMS number format (E.164 required): {r}")
            elif self.channel == MessageChannel.EMAIL:
                email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
                if not re.fullmatch(email_regex, r):
                    raise IntegrationValidationException(f"Invalid email address: {r}")
            elif self.channel == MessageChannel.WHATSAPP:
                if not re.fullmatch(r'^\d{1,15}$', r):
                    raise IntegrationValidationException(f"Invalid WhatsApp number: {r}")
            elif self.channel in {MessageChannel.PUSH, MessageChannel.WEB_PUSH}:
                if len(r) > 256:
                    raise IntegrationValidationException(f"Device token too long: {r}")

        return self

    model_config = ConfigDict(
        json_encoders = {
            datetime: lambda v: v.isoformat()
        },
        json_schema_extra = {
            "examples": [
                {
                    "channel": "sms",
                    "to": {
                        "recipient": "+1234567890",
                        "cc_recipient": "",
                        "bcc_recipient": ""
                    },
                    "payload": {
                        "text": "Your code is 12345",
                        "sender_id": "MYBRAND",
                        "unicode": False
                    }
                },
                {
                    "channel": "whatsapp",
                    "to": {
                        "recipient": "1234567890",
                        "cc_recipient": "",
                        "bcc_recipient": ""
                    },
                    "payload": {
                        "template_name": "order_confirmation",
                        "template_variables": {
                            "order_number": "12345",
                            "delivery_date": "2023-12-25"
                        },
                        "language_code": "en"
                    },
                    "extras": {
                        "order_id": "12345"
                    }
                }
            ]
        }
    )

    @staticmethod
    def builder() -> MessageRequestBuilder:
        """Create a new MessageRequestBuilder instance"""
        return MessageRequestBuilder()
