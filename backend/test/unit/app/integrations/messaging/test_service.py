import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch

from _pytest.monkeypatch import MonkeyPatch
from kink import di
from parameterized import parameterized

from main.app.config.bootstrap import bootstrap_di
bootstrap_di()
from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate
from main.appodus_utils import Utils
from main.appodus_utils.integrations.exception.exceptions import IntegrationValidationException, IntegrationRateLimitException, \
    IntegrationException
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel, MessageRequest, MessageRecipient,
    EmailPayloadRequest, SmsPayload, WhatsappPayload,
    PushPayload, WebPushPayload, WhatsappMediaType,
    WhatsappButtonType, PushPriority, MessageStatus, MessageProviderName, AttachmentRequest, MessagePriority
)

rate_limiter: RateLimiter = di[RateLimiter]


class TestMessagingService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):

        """Create a temporary file for testing."""
        self.temp_file = NamedTemporaryFile(delete=False)
        self.temp_file_path = Path(self.temp_file.name)
        self.test_file_path_content = b"Test file content"
        self.temp_file.write(self.test_file_path_content)
        self.temp_file.close()  # Close so we can use it in tests

        # Register test logger in DI
        # di['logger'] = MagicMock()

        # Patch the resilience manager before importing anything
        # with patch('main.appodus_utils.integrations.messaging.service.resilience_manager',
        #            new=test_resilience_manager):
        # Create mock dependencies
        self.monkey_patch = MonkeyPatch()
        self.mock_router = AsyncMock()
        self.mock_template_service = AsyncMock()
        self.mock_message_service = AsyncMock()
        self.mock_dlq = AsyncMock()

        # Create circuit breaker mock that just passes through
        # self.mock_circuit = MagicMock()
        # self.mock_circuit.__call__ = lambda *args, **kwargs: lambda f: f  # Complete bypass
        #
        # self.circuit_patcher = patch(
        #     'main.appodus_utils.integrations.messaging.service.resilience_manager.messaging_circuit_breaker',
        #     new=self.mock_circuit)
        # self.circuit_patcher.start()

        # Now import the service after patching
        from main.appodus_utils.integrations.messaging.service import MessagingService
        # Initialize service with mocks
        self.service = MessagingService(
            router=self.mock_router,
            template_service=self.mock_template_service,
            message_service=self.mock_message_service,
            dlq=self.mock_dlq,
            rate_limiter=rate_limiter
        )

        # Common test data
        self.test_message_id = "msg_123"
        self.test_recipient = "+2347039018727"
        self.test_email = "kingsley.ezenwere@gmail.com"
        self.test_push_token = "push_token_123"
        self.test_extras = {"trace_id": "12345"}
        self.test_sent_at = Utils.datetime_now()

    async def asyncTearDown(self):
        """Clean up temporary file."""
        if self.temp_file_path.exists():
            self.temp_file_path.unlink()
        """Clean up MonkeyMock"""
        self.monkey_patch.undo()
        # di.clear_cache()
        # Reset all mocks
        for mock in [
            self.mock_router,
            self.mock_template_service,
            self.mock_message_service,
            self.mock_dlq
        ]:
            mock.reset_mock()

    # SMS Tests
    @parameterized.expand([
        ("plain_text", None, None, False, False),
        ("with_template", AvailableTemplate.TWO_FA, {"name": "John"}, False, False),
        ("unicode", None, None, True, False),
        ("flash_sms", None, None, False, True)
    ])
    async def test_send_sms(self, name, template, template_vars, unicode, flash):
        # Reset mocks for this test case
        # self.mock_router.reset_mock()
        # self.mock_template_service.reset_mock()

        payload = SmsPayload(
            text="Your verification code is 123456" if not template else None,
            unicode=unicode,
            flash=flash,
            sender_id="veriprops"
        )

        request = MessageRequest(
            channel=MessageChannel.SMS,
            to=MessageRecipient(recipient=self.test_recipient),
            payload=payload,
            template=template,
            template_variables=template_vars,
            extras=self.test_extras
        )

        # Mock template rendering if template is used
        if request.template:
            self.mock_template_service.render_message.return_value = "Hello John, your code is 123456"

        # Mock successful send
        self.mock_router.send_message.return_value = MagicMock(
            provider_id=self.test_message_id,
            status=MessageStatus.SENT,
            provider=MessageProviderName.TERMII_SMS,
            sent_at=self.test_sent_at
        )

        result = await self.service.send_message(request)

        # Assertions
        self.assertEqual(result.provider_id, self.test_message_id)
        self.assertEqual(result.status, MessageStatus.SENT)
        self.assertEqual(result.provider, MessageProviderName.TERMII_SMS)
        self.assertEqual(result.sent_at, self.test_sent_at)
        if template:
            self.mock_template_service.render_message.assert_called_once_with(
                channel=MessageChannel.SMS,
                template_name=template,
                context=template_vars
            )
        self.mock_router.send_message.assert_called_once()

    # Email Tests
    @parameterized.expand([
        ("plain_text", "Welcome john", None, None, False),
        ("html_only", None, "<h1>Welcome john</h1>", None, False),
        ("with_template", None, None, AvailableTemplate.NEW_USER_WELCOME, False),
        ("with_attachments", None, "<h1>Welcome john</h1>", None, True),
    ])
    async def test_send_email(self, name, text, html, template, with_attachments=False):
        attachments = [
            AttachmentRequest(file_path=self.temp_file_path, filename="doc.pdf")
        ] if with_attachments else None

        template_vars = {"name": "John"} if template else None

        payload = EmailPayloadRequest(
            subject="Welcome!",
            text=text,
            html=html,
            from_email="noreply@example.com",
            attachments=attachments
        )

        request = MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(recipient=self.test_email),
            payload=payload,
            template=template,
            template_variables=template_vars,
            extras=self.test_extras
        )

        if request.template:
            self.mock_template_service.render_message.return_value = "<h1>Hello John</h1>"

        self.mock_router.send_message.return_value = MagicMock(
            provider_id=self.test_message_id,
            status=MessageStatus.SENT,
            provider=MessageProviderName.MAILJET,
            sent_at=self.test_sent_at
        )

        result = await self.service.send_message(request)

        # Assertions
        self.assertEqual(result.provider_id, self.test_message_id)
        self.assertEqual(result.status, MessageStatus.SENT)
        self.assertEqual(result.provider, MessageProviderName.MAILJET)
        self.assertEqual(result.sent_at, self.test_sent_at)
        if template:
            self.mock_template_service.render_message.assert_called_once_with(
                channel=MessageChannel.EMAIL,
                template_name=template,
                context=template_vars
            )
        self.mock_router.send_message.assert_called_once()

    # WhatsApp Tests
    @parameterized.expand([
        ("text_message", None, None, None, None, "Hello there", False, False),
        ("template_message", AvailableTemplate.ESCROW_INITIATED, {"name": "John"}, "en", None, None, False, False),
        ("image_message", None, None, None, WhatsappMediaType.IMAGE, "Check this out", False, False),
        ("document_message", None, None, None, WhatsappMediaType.DOCUMENT, "Your document", False, False),
        ("interactive_buttons", None, None, None, None, None, True, False),
        ("list_sections", None, None, None, None, None, False, True)
    ])
    async def test_send_whatsapp(
            self, name, template, template_vars, language,
            media_type, caption, with_buttons, with_sections
    ):
        buttons = [
            {
                "type": WhatsappButtonType.REPLY,
                "title": "Confirm",
                "payload": "confirm_123"
            }
        ] if with_buttons else None

        sections = [
            {
                "title": "Options",
                "rows": [
                    {"id": "opt1", "title": "Option 1"},
                    {"id": "opt2", "title": "Option 2"}
                ]
            }
        ] if with_sections else None

        payload = WhatsappPayload(
            text="Hello" if name == "text_message" else None,
            media_url="https://example.com/image.jpg" if media_type else None,
            media_type=media_type,
            caption=caption,
            language_code=language or "en",
            buttons=buttons,
            sections=sections,
            has_local_template=True if template else False
        )

        recipient = self.test_recipient[1:]  # Removes first character, the +
        request = MessageRequest(
            channel=MessageChannel.WHATSAPP,
            to=MessageRecipient(recipient=recipient),
            payload=payload,
            template=template,
            template_variables=template_vars,
            extras=self.test_extras
        )

        if request.template:
            self.mock_template_service.render_message.return_value = \
                "veriprops: Your OTP is *12234*. Valid for 5 minutes."

        self.mock_router.send_message.return_value = MagicMock(
            provider_id=self.test_message_id,
            status=MessageStatus.SENT,
            provider=MessageProviderName.WHATSAPP_BUSINESS,
            sent_at=self.test_sent_at
        )

        result = await self.service.send_message(request)

        # Assertions
        self.assertEqual(result.provider_id, self.test_message_id)
        self.assertEqual(result.status, MessageStatus.SENT)
        self.assertEqual(result.provider, MessageProviderName.WHATSAPP_BUSINESS)
        self.assertEqual(result.sent_at, self.test_sent_at)
        if template:
            self.mock_template_service.render_message.assert_called_once_with(
                channel=MessageChannel.WHATSAPP,
                template_name=template,
                context=template_vars
            )
        self.mock_router.send_message.assert_called_once()

    # Push Notification Tests
    @parameterized.expand([
        ("android_push", "android", None, False),
        ("ios_push", "ios", None, False),
        ("high_priority", "ios", PushPriority.HIGH, False),
        ("with_image", "android", None, True)
    ])
    async def test_send_push(self, name, platform, priority, with_image):
        payload = PushPayload(
            title="Notification",
            body="You have a new message",
            priority=priority or PushPriority.NORMAL,
            image_url="https://example.com/image.jpg" if with_image else None,
            data={"action": "open_message", "id": "123"}
        )

        request = MessageRequest(
            channel=MessageChannel.PUSH,
            to=MessageRecipient(recipient=self.test_push_token),
            payload=payload,
            extras={**self.test_extras, "platform": platform}
        )

        self.mock_router.send_message.return_value = MagicMock(
            provider_id=self.test_message_id,
            status=MessageStatus.SENT,
            provider=MessageProviderName.FIREBASE_PUSH,
            sent_at=self.test_sent_at
        )

        result = await self.service.send_message(request)

        # Assertions
        self.assertEqual(result.provider_id, self.test_message_id)
        self.assertEqual(result.status, MessageStatus.SENT)
        self.assertEqual(result.provider, MessageProviderName.FIREBASE_PUSH)
        self.assertEqual(result.sent_at, self.test_sent_at)
        self.mock_router.send_message.assert_called_once()

    async def test_send_web_push(self):
        payload = WebPushPayload(
            title="Web Notification",
            body="New update available",
            icon_url="https://example.com/icon.png",
            url="https://example.com/update"
        )

        request = MessageRequest(
            channel=MessageChannel.WEB_PUSH,
            to=MessageRecipient(recipient=self.test_push_token),
            payload=payload,
            extras=self.test_extras
        )

        self.mock_router.send_message.return_value = MagicMock(
            provider_id=self.test_message_id,
            status=MessageStatus.SENT,
            provider=MessageProviderName.WEB_PUSH,
            sent_at=self.test_sent_at
        )

        result = await self.service.send_message(request)

        self.assertEqual(result.provider_id, self.test_message_id)
        self.mock_router.send_message.assert_called_once()

    # Bulk Messaging Tests
    async def test_send_bulk_messages(self):
        count = 3
        requests = [
            MessageRequest(
                channel=MessageChannel.SMS,
                to=MessageRecipient(recipient=f"{self.test_recipient}{i}"),
                payload=SmsPayload(text=f"Message {i}"),
                priority=MessagePriority.NORMAL
            )
            for i in range(count)
        ]

        self.mock_router.send_message.side_effect = [
            MagicMock(
                provider_id=f'{self.test_message_id}_{i}',
                status=MessageStatus.SENT,
                provider=MessageProviderName.WEB_PUSH,
                sent_at=self.test_sent_at
            ) for i in range(count)
        ]

        result = await self.service.send_bulk(requests)

        self.assertEqual(result["total"], count)
        self.assertEqual(result["success"], count)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(self.mock_router.send_message.call_count, count)

    # Failure Scenarios
    @parameterized.expand([
        ("validation_failure", IntegrationValidationException("Invalid")),
        ("rate_limit", IntegrationRateLimitException(key="test_key", reset_at= Utils.datetime_now())),
        ("provider_failure", IntegrationException("Provider error")),
        ("unexpected_error", Exception("Unexpected"))
    ])
    async def test_send_message_failures(self, name, exception):
        request = MessageRequest(
            channel=MessageChannel.SMS,
            to=MessageRecipient(recipient=self.test_recipient),
            payload=SmsPayload(text="Test")
        )

        self.mock_router.send_message.side_effect = exception

        if isinstance(exception, IntegrationRateLimitException):
            # Fail check limit
            def mock_check_limit(*args, **kwargs):
                raise exception

            self.monkey_patch.setattr(rate_limiter, "check_limit", mock_check_limit)

        with self.assertRaises(IntegrationException):
            await self.service.send_message(request)

        if isinstance(exception, IntegrationRateLimitException):
            # Not added to dlq
            self.mock_dlq.add_to_dlq.assert_not_called()
        else:
            self.mock_dlq.add_to_dlq.assert_called_once()

    # DLQ Tests
    async def test_dlq_retry_processing(self):
        self.mock_dlq.process_retries.return_value = {
            "processed": 2,
            "success": 1,
            "failures": 1
        }

        result = await self.service.process_dlq_retries()

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failures"], 1)
        self.mock_dlq.process_retries.assert_called_once_with(100)

    # Status Checking
    async def test_get_message_status(self):
        test_message = MagicMock(
            id=self.test_message_id,
            status="pending",
            provider="twilio_sms",
            provider_id="prov_123"
        )
        self.mock_message_service.get_message_by_id.return_value = test_message
        self.mock_router.get_message_status.return_value = "delivered"

        result = await self.service.get_message_status(self.test_message_id)

        self.assertEqual(result.status, "delivered")
        self.mock_router.get_message_status.assert_called_once_with(
            "twilio_sms",
            "prov_123"
        )


if __name__ == "__main__":
    unittest.main()
