"""
Messaging System Module

This module provides a flexible and extensible framework for sending messages through various channels
(Email, SMS, WhatsApp, Push Notifications, Web Push). It follows the Strategy Pattern to allow
easy addition of new messaging channels.

The system is composed of:
- MessageRequestBuilder: Abstract base class for building message requests for specific channels
- ChannelSender: Abstract base class for sending messages through specific channels
- Concrete implementations for each supported channel

Key Components:
1. Builders: Construct channel-specific message payloads and requests
2. Senders: Handle the actual delivery of messages through the messaging service
3. Models: Define the data structures used for message requests and responses
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List

from kink import di, inject

from main.appodus_utils.integrations.messaging.config import MessagingConfig
from main.appodus_utils.integrations.messaging.models import (
    MessageRequestRecipient,
    EmailPayloadRequest,
    MessageRequest,
    MessageChannel,
    MessageRecipient,
    SmsPayload, MultiChannelMessageRequest
)
from main.appodus_utils.integrations.messaging.service import MessagingService
from main.appodus_utils.integrations.messaging.templating.model_template_service import ModelTemplateService
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

logger: logging.Logger = di['logger']


@inject
class MessageDispatcher:
    """
    Unified sender for multiple message channels with bulk support.

    Handles sending messages across different channels (email, SMS, WhatsApp, etc.)
    with support for both individual and bulk operations.
    """

    def __init__(self,
                 messaging_service: MessagingService,
                 template_service: ModelTemplateService):
        """
        Initialize with messaging service.

        Args:
            messaging_service: The core messaging service that handles actual delivery
        """
        config = MessagingConfig.from_settings()

        self.messaging_service = messaging_service
        self._senders = {
            MessageChannel.EMAIL: EmailMessageHandler(messaging_service, config),
            MessageChannel.SMS: SmsMessageHandler(messaging_service, config),
            MessageChannel.WHATSAPP: WhatsAppMessageHandler(messaging_service, template_service),
            MessageChannel.PUSH: PushNotificationMessageHandler(messaging_service, template_service),
            MessageChannel.WEB_PUSH: WebPushMessageHandler(messaging_service, template_service)
        }

    async def dispatch_bulk(self,
                            requests: List[MultiChannelMessageRequest]) -> Dict:
        """
                Process multiple send requests across different channels.

                Args:
                    requests: List of send requests with channels

                Returns:
                    Dict: Summary with success/failure counts
                        {
                            "total": int,
                            "success": int,
                            "failures": int
                        }

                Example:
                    ... await sender.send_bulk([
                    ...     UserMessageSenderRequest(
                    ...         recipient=...,
                    ...         template=...,
                    ...         channels=[MessageChannel.EMAIL]
                    ...     ),
                    ...     UserMessageSenderRequest(
                    ...         recipient=...,
                    ...         template=...,
                    ...         channels=[MessageChannel.SMS, MessageChannel.WHATSAPP]
                    ...     )
                    ... ])
                """
        message_requests = []
        for request in requests:
            message_requests.extend(
                self._build_requests_for_channels(
                    request.recipient,
                    request.template,
                    request.context,
                    request.channels
                )
            )

        return await self.messaging_service.send_bulk(message_requests)

    async def dispatch_to_channels(self,
                                   request: MultiChannelMessageRequest) -> Dict:
        """
        Send a single message through multiple channels.

        Args:
            request: Send request with multiple channels

        Returns:
            Dict: Summary with success/failure counts

        Note:
            This is a convenience method that wraps send_bulk for a single request
        """
        return await self.dispatch_bulk([request])

    def _get_channel_sender(self, channel: MessageChannel) -> 'MessageChannelHandler':
        """Get sender instance for the specified channel."""
        sender = self._senders.get(channel)
        if not sender:
            raise ValueError(f"Unsupported channel: {channel}")
        return sender

    def _build_requests_for_channels(
            self,
            recipient: MessageRequestRecipient,
            template: AvailableTemplate,
            context: Dict[str, Any],
            channels: List[MessageChannel]
    ) -> List[MessageRequest]:
        """Build MessageRequest objects for each channel."""
        requests = []
        for channel in channels:
            try:
                sender = self._get_channel_sender(channel)
                request = sender.request_builder.build_request(
                    recipient=recipient,
                    template=template,
                    context=context
                )
                requests.append(request)
            except Exception as e:
                logger.error(
                    f"Failed to build request for channel '{channel.value}': {str(e)}",
                    exc_info=True
                )
        return requests


class MessageRequestBuilder(ABC):
    """
    Abstract base class for building message requests for specific channels.

    Implementations should handle channel-specific payload construction and validation.
    """

    @abstractmethod
    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]) -> MessageRequest:
        """
        Construct a MessageRequest for the specific channel.

        Args:
            recipient: The recipient information including contact details and user ID
            template: The template enum to use for the message
            context: Variables to interpolate into the template and channel-specific parameters

        Returns:
            MessageRequest: Fully constructed message request ready for sending

        Raises:
            ValueError: If required recipient information is missing
            IntegrationValidationException: If message validation fails
        """
        pass


class MessageChannelHandler(ABC):
    """
    Abstract base class for sending messages through specific channels.

    Concrete implementations should initialize with the appropriate MessageRequestBuilder.
    """

    def __init__(self,
                 messaging_service: MessagingService,
                 request_builder: MessageRequestBuilder):
        """
        Initialize the sender with messaging service and request builder.

        Args:
            messaging_service: Service for actually delivering messages
            request_builder: Builder for constructing channel-specific requests
        """
        self.messaging_service = messaging_service
        self.request_builder = request_builder

    async def send(self,
                   recipient: MessageRequestRecipient,
                   template: AvailableTemplate,
                   context: Dict[str, Any]) -> bool:
        """
        Send a message through the channel.

        Args:
            recipient: The message recipient
            template: The template enum to use
            context: Variables for template interpolation and channel parameters

        Returns:
            bool: True if message was successfully sent, False otherwise

        Examples:
            ... sender = EmailSender(messaging_service, config)
            ... await sender.send(
            ...     recipient=MessageRequestRecipient(email="user@example.com"),
            ...     template=AvailableTemplate.WELCOME_EMAIL,
            ...     context={"name": "John"}
            ... )
            True
        """
        try:
            request = self.request_builder.build_request(recipient, template, context)
            await self.messaging_service.send_message(request)
            return True
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            return False
        except Exception as e:
            logger.error(f"Send failed: {e}", exc_info=True)
            return False

    async def send_bulk(self,
                        recipients: List[MessageRequestRecipient],
                        template: AvailableTemplate,
                        context: Dict[str, Any]) -> Dict:
        """
        Send to multiple recipients through this channel.

        Args:
            recipients: List of recipients
            template: Template to use
            context: Base context (can be overridden per recipient)

        Returns:
            Dict: Result summary with counts

        Example:
            # Bulk email sending
            sender = EmailSender(messaging_service, config)
            results = await sender.send_bulk(
                recipients=[...],
                template=AvailableTemplate.NEWSLETTER,
                context={"month": "January"}
            )
        """
        message_requests = []
        for recipient in recipients:
            try:
                request = self.request_builder.build_request(
                    recipient=recipient,
                    template=template,
                    context=context
                )
                message_requests.append(request)
            except Exception as e:
                logger.error(f"Failed to build request for {recipient}: {e}")
                continue

        return await self.messaging_service.send_bulk(message_requests)


class EmailRequestBuilder(MessageRequestBuilder):
    """
    Builder for constructing email message requests with support for:
    - HTML and text content
    - Attachments
    - Scheduled sending
    - CC/BCC recipients
    - Custom headers and categories
    """

    def __init__(self, config: MessagingConfig):
        """
        Initialize with email configuration.

        Args:
            config: Dictionary containing:
                - from_email: Sender email (required)
                - from_name: Sender name (required)
                - reply_to: Reply-to address (optional), defaults to 'from_email'
                - categories: Default categories (optional)
                - headers: Default headers (optional)
                - priority: Default priority (optional)
                - sandbox_mode: Default sandbox mode (optional)

        Example:
            config = {
                "from_email": "noreply@company.com",
                "from_name": "Company Support",
                "reply_to": "support@company.com",
                "categories": ["transactional"]
            }
        """
        self.from_email = config.from_email
        self.from_name = config.from_name
        self.reply_to = self.from_email
        self.default_categories = config.categories
        self.default_headers = config.headers
        self.default_priority = config.priority
        self.default_sandbox = config.sandbox_mode
        self.config = config

    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]):
        """
        Build an email MessageRequest.

        Examples:
            # Simple email
            builder.build_request(
                recipient=MessageRequestRecipient(email="user@example.com"),
                template=AvailableTemplate.WELCOME,
                context={"name": "John"}
            )

            # Email with attachments and CC
            builder.build_request(
                recipient=MessageRequestRecipient(
                    email="user@example.com",
                    cc_recipient=["manager@example.com"],
                    name="John Doe"
                ),
                template=AvailableTemplate.INVOICE,
                context={
                    "attachments": [{"filename": "invoice.pdf", "content": "..."}],
                    "priority": MessagePriority.HIGH
                }
            )
        """
        if not recipient.email:
            raise ValueError("Email error: Email address is required")

        html = context.get('html')
        text = context.get('text')
        if not html and not text and not template:
            raise ValueError("Email error: Either html, text content or a template is required")

        subject = self.config.get_subject(template.value)
        if not subject:
            raise ValueError("Email error: Subject is required")

        payload = EmailPayloadRequest(
            subject=subject,
            html=html,
            text=text,
            from_email=self.from_email,
            from_name=self.from_name,
            reply_to=context.get('reply_to', self.reply_to),
            attachments=context.get('attachments', []),
            headers={**self.default_headers, **context.get('headers', {})},
            categories=self.default_categories + context.get('categories', []),
            send_at=context.get('schedule_at')
        )

        return MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(
                recipient=recipient.email,
                name=recipient.fullname,
                cc_recipient=recipient.cc_recipient,
                bcc_recipient=recipient.bcc_recipient
            ),
            payload=payload,
            template=template,
            template_variables=context,
            schedule_at=context.get("schedule_at"),
            sandbox_mode=context.get("sandbox_mode"),
            extras={
                "user_id": recipient.user_id,
                **context.get('extras', {})
            }
        )


class EmailMessageHandler(MessageChannelHandler):
    """
    Email channel sender implementation.

    Examples:
        # Basic usage
        sender = EmailSender(messaging_service, config)
        await sender.send(
            recipient=MessageRequestRecipient(email="user@example.com"),
            template=AvailableTemplate.WELCOME,
            context={"name": "John"}
        )

        # With error handling
        success = await sender.send(...)
        if not success:
            # Handle failure
    """

    def __init__(self, messaging_service: MessagingService, config: MessagingConfig):
        super().__init__(messaging_service, EmailRequestBuilder(config))


class SmsRequestBuilder(MessageRequestBuilder):
    """
    Builder for SMS messages with support for:
    - Concatenated SMS (up to 1600 chars)
    - Unicode messages
    - Flash SMS
    - TTL (time-to-live)
    """

    def __init__(self, config: MessagingConfig):
        """
        Initialize with SMS configuration.

        Args:
            config: Dictionary containing:
                - sender_id: Alphanumeric sender ID (required)
                - ttl: Default time-to-live (optional, default: 3600)
                - unicode: Default unicode setting (optional)
                - flash: Default flash setting (optional)

        Example:
            config = {
                "sender_id": "veriprops",
                "ttl": 7200,
                "unicode": True
            }
        """
        self.sender_id = config.sms_sender_id
        self.default_ttl = config.sms_ttl
        self.default_unicode = False
        self.default_flash = False

    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]):
        """
        Build an SMS MessageRequest.

        Examples:
            # Simple SMS
            builder.build_request(
                recipient=MessageRequestRecipient(phone="+1234567890"),
                template=AvailableTemplate.OTP,
                context={"code": "123456"}
            )

            # Flash SMS with custom TTL
            builder.build_request(
                recipient=MessageRequestRecipient(phone="+1234567890"),
                template=None,
                context={
                    "text": "URGENT: System going down at 10PM",
                    "flash": True,
                    "ttl": 1800
                }
            )
        """
        if not recipient.phone:
            raise ValueError("SMS error: Phone number is required")

        text = context.get('text')
        if not text and not template:
            raise ValueError("SMS error: Either text content or a template is required")

        payload = SmsPayload(
            text=text,
            sender_id=context.get('sender_id', self.sender_id),
            unicode=context.get('unicode', self.default_unicode),
            flash=context.get('flash', self.default_flash),
            ttl=context.get('ttl', self.default_ttl)
        )

        return MessageRequest(
            channel=MessageChannel.SMS,
            to=MessageRecipient(recipient=recipient.phone),
            payload=payload,
            template=template,
            schedule_at=context.get("schedule_at"),
            sandbox_mode=context.get("sandbox_mode"),
            extras={
                "user_id": recipient.user_id,
                **context.get('extras', {})
            }
        )


class SmsMessageHandler(MessageChannelHandler):
    """
    SMS channel sender implementation.

    Examples:
        # Using template
        sender = SmsSender(messaging_service, config)
        await sender.send(
            recipient=MessageRequestRecipient(phone="+1234567890"),
            template=AvailableTemplate.APPOINTMENT_REMINDER,
            context={"time": "2:00 PM"}
        )

        # Direct text message
        await sender.send(
            recipient=MessageRequestRecipient(phone="+1234567890"),
            template=None,
            context={"text": "Your package has shipped"}
        )
    """

    def __init__(self, messaging_service: MessagingService, config: MessagingConfig):
        super().__init__(messaging_service, SmsRequestBuilder(config))


class WhatsAppRequestBuilder(MessageRequestBuilder):
    """
    Builder for WhatsApp messages with support for:
    - Template messages
    - Interactive messages
    - Media messages (images, documents)
    - Language localization
    """

    def __init__(self, template_service: ModelTemplateService):
        """
        Initialize with template service.

        Args:
            template_service: Service for rendering WhatsApp templates
        """
        self.template_service = template_service

    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]):
        """
        Build a WhatsApp MessageRequest.

        Examples:
            # Template message
            builder.build_request(
                recipient=MessageRequestRecipient(phone="1234567890"),
                template=AvailableTemplate.ORDER_CONFIRMATION,
                context={
                    "variables": {"order_id": "12345"},
                    "language": "en_US"
                }
            )

            # Interactive message
            builder.build_request(
                recipient=MessageRequestRecipient(phone="1234567890"),
                template=None,
                context={
                    "type": "interactive",
                    "interactive_data": {...}
                }
            )
        """
        if not recipient.phone:
            raise ValueError("WhatsApp error: Phone number is required")

        if template:
            payload = self.template_service.render_whatsapp_payload(template, context)
        else:
            payload = context.get('payload')
            if not payload:
                raise ValueError("Either template or direct payload is required")

        return MessageRequest(
            channel=MessageChannel.WHATSAPP,
            to=MessageRecipient(recipient=recipient.phone),
            payload=payload,
            template=template,
            schedule_at=context.get("schedule_at"),
            sandbox_mode=context.get("sandbox_mode"),
            extras={
                "user_id": recipient.user_id,
                **context.get('extras', {})
            }
        )


class WhatsAppMessageHandler(MessageChannelHandler):
    """
    WhatsApp channel sender implementation.

    Examples:
        # Template message
        sender = WhatsAppSender(messaging_service, template_service)
        await sender.send(
            recipient=MessageRequestRecipient(phone="1234567890"),
            template=AvailableTemplate.SHIPPING_UPDATE,
            context={
                "variables": {"tracking_no": "ABC123"},
                "language": "en_GB"
            }
        )
    """

    def __init__(self, messaging_service: MessagingService, template_service: ModelTemplateService):
        super().__init__(messaging_service, WhatsAppRequestBuilder(template_service))


class PushNotificationRequestBuilder(MessageRequestBuilder):
    """
    Builder for mobile push notifications with support for:
    - iOS and Android platforms
    - Rich notifications (images, actions)
    - Priority levels
    - Custom sound and badges
    """

    def __init__(self, template_service: ModelTemplateService):
        """
        Initialize with template service.

        Args:
            template_service: Service for rendering push notification templates
        """
        self.template_service = template_service

    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]):
        """
        Build a push notification MessageRequest.

        Examples:
            # iOS notification
            builder.build_request(
                recipient=MessageRequestRecipient(ios_push_token="abcd1234"),
                template=AvailableTemplate.NEW_MESSAGE,
                context={
                    "sound": "chime.wav",
                    "badge": 5
                }
            )

            # Android high-priority
            builder.build_request(
                recipient=MessageRequestRecipient(android_push_token="efgh5678"),
                template=None,
                context={
                    "title": "Urgent!",
                    "body": "Server down!",
                    "priority": "high"
                }
            )
        """
        push_token, platform = self._get_push_token(recipient)
        if not push_token:
            raise ValueError("No valid push token available")

        if template:
            payload = self.template_service.render_push_payload(template, context)
        else:
            payload = context.get('payload')
            if not payload:
                raise ValueError("Either template or direct payload is required")

        return MessageRequest(
            channel=MessageChannel.PUSH,
            to=MessageRecipient(recipient=push_token),
            payload=payload,
            template=template,
            schedule_at=context.get("schedule_at"),
            sandbox_mode=context.get("sandbox_mode"),
            extras={
                "user_id": recipient.user_id,
                **context.get('extras', {})
            }
        )

    @staticmethod
    def _get_push_token(recipient):
        """Extract platform-specific push token"""
        if recipient.ios_push_token:
            return recipient.ios_push_token, "ios"
        if recipient.android_push_token:
            return recipient.android_push_token, "android"
        return None, None


class PushNotificationMessageHandler(MessageChannelHandler):
    """
    Push notification channel sender implementation.

    Examples:
        # iOS notification
        sender = PushNotificationSender(messaging_service, template_service)
        await sender.send(
            recipient=MessageRequestRecipient(ios_push_token="abcd1234"),
            template=AvailableTemplate.NEW_MESSAGE,
            context={"sound": "default"}
        )
    """

    def __init__(self, messaging_service: MessagingService, template_service: ModelTemplateService):
        super().__init__(messaging_service, PushNotificationRequestBuilder(template_service))


class WebPushRequestBuilder(MessageRequestBuilder):
    """
    Builder for web push notifications with support for:
    - Browser-specific payloads
    - Notification actions
    - Vibration patterns
    - Service worker handling
    """

    def __init__(self, template_service: ModelTemplateService):
        """
        Initialize with template service.

        Args:
            template_service: Service for rendering web push templates
        """
        self.template_service = template_service

    def build_request(self,
                      recipient: MessageRequestRecipient,
                      template: AvailableTemplate,
                      context: Dict[str, Any]):
        """
        Build a web push MessageRequest.

        Examples:
            # Basic notification
            builder.build_request(
                recipient=MessageRequestRecipient(web_push_token="subscription_id"),
                template=AvailableTemplate.PROMOTIONAL_OFFER,
                context={}
            )

            # With actions
            builder.build_request(
                recipient=MessageRequestRecipient(web_push_token="subscription_id"),
                template=None,
                context={
                    "title": "New message",
                    "actions": [
                        {"action": "reply", "title": "Reply"}
                    ]
                }
            )
        """
        if not recipient.web_push_token:
            raise ValueError("Web Push error: Web push token is required")

        if template:
            payload = self.template_service.render_web_push_payload(template, context)
        else:
            payload = context.get('payload')
            if not payload:
                raise ValueError("Web Push error: Either template or direct payload is required")

        return MessageRequest(
            channel=MessageChannel.WEB_PUSH,
            to=MessageRecipient(recipient=recipient.web_push_token),
            payload=payload,
            template=template,
            schedule_at=context.get("schedule_at"),
            sandbox_mode=context.get("sandbox_mode"),
            extras={
                "user_id": recipient.user_id,
                **context.get('extras', {})
            }
        )


class WebPushMessageHandler(MessageChannelHandler):
    """
    Web push channel sender implementation.

    Examples:
        sender = WebPushSender(messaging_service, template_service)
        await sender.send(
            recipient=MessageRequestRecipient(web_push_token="sub123"),
            template=AvailableTemplate.NEW_COMMENT,
            context={"username": "john_doe"}
        )
    """

    def __init__(self, messaging_service: MessagingService, template_service: ModelTemplateService):
        super().__init__(messaging_service, WebPushRequestBuilder(template_service))
