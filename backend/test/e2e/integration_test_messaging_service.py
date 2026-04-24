# import asyncio
# import json
# from datetime import datetime
# from unittest import IsolatedAsyncioTestCase
#
# from sqlalchemy.ext.asyncio import async_session
# from testcontainers.core.container import DockerContainer
# from testcontainers.core.waiting_utils import wait_for_logs
# from wiremock.client import (
#     Mappings,
#     Mapping,
#     MappingRequest,
#     MappingResponse,
#     HttpMethods
# )
# from wiremock.testing.testcontainer import WireMockContainer
#
# # Application imports
# from main.appodus_utils.integrations.messaging.models import (
#     MessageRequest
# )
# from main.appodus_utils.integrations.messaging.providers.email.sendgrid import SendGridEmailProvider
# from main.appodus_utils.integrations.messaging.providers.push.firebase import FirebasePushProvider
# from main.appodus_utils.integrations.messaging.providers.sms.twilio import (TwilioSMSProvider)
# from main.appodus_utils.integrations.messaging.providers.whatsapp.whatsapp_business import WhatsAppBusinessProvider
#
#
# class TestMessagingService(IsolatedAsyncioTestCase):
#     @classmethod
#     async def asyncSetUpClass(cls):
#         # Start WireMock for mocking external APIs
#         cls.wiremock_container = WireMockContainer()
#         cls.wiremock_container.start()
#         wait_for_logs(cls.wiremock_container, "port:", timeout=30)
#         cls.wiremock_url = cls.wiremock_container.get_url("__admin")
#
#         # Start PostgreSQL container
#         cls.postgres_container = DockerContainer("postgres:13")
#         cls.postgres_container.with_env("POSTGRES_USER", "test")
#         cls.postgres_container.with_env("POSTGRES_PASSWORD", "test")
#         cls.postgres_container.with_env("POSTGRES_DB", "testdb")
#         cls.postgres_container.with_exposed_ports(5432)
#         cls.postgres_container.start()
#         wait_for_logs(cls.postgres_container, "database system is ready to accept connections", timeout=30)
#
#         # Setup database connection
#         cls.db_url = (
#             f"postgresql+asyncpg://test:test@"
#             f"{cls.postgres_container.get_container_host_ip()}:"
#             f"{cls.postgres_container.get_exposed_port(5432)}/testdb"
#         )
#
#         # Setup WireMock stubs for providers
#         cls._setup_wiremock_stubs()
#
#         # Initialize services
#         session_factory = async_session(cls.db_url)
#         cls.message_repo = SQLMessageRepository(session_factory)
#         cls.dlq_repo = SQLDLQRepository(session_factory)
#         cls.template_service = TemplateService()
#
#         # Initialize providers with WireMock URLs
#         cls.providers = [
#             TwilioSMSProvider(base_url=cls.wiremock_url),
#             SendGridEmailProvider(base_url=cls.wiremock_url),
#             WhatsAppBusinessProvider(base_url=cls.wiremock_url),
#             FirebasePushProvider(base_url=cls.wiremock_url)
#         ]
#
#         cls.router = MessageRouter(cls.providers)
#         cls.service = MessagingService(
#             router=cls.router,
#             template_service=cls.template_service,
#             message_repo=cls.message_repo,
#             dlq_repo=cls.dlq_repo
#         )
#
#         # Create database tables
#         await cls._create_tables()
#
#     @classmethod
#     async def asyncTearDownClass(cls):
#         cls.postgres_container.stop()
#         cls.wiremock_container.stop()
#
#     @classmethod
#     def _setup_wiremock_stubs(cls):
#         """Configure WireMock stubs for all provider APIs"""
#         # Twilio SMS stub
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.POST,
#                     url_path="/api/sms/send"
#                 ),
#                 response=MappingResponse(
#                     status=200,
#                     body=json.dumps({
#                         "sid": "SM123",
#                         "status": "queued"
#                     })
#                 ),
#                 persistent=False
#             )
#         )
#
#         # WhatsApp stub
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.POST,
#                     url_path="/v1/messages"
#                 ),
#                 response=MappingResponse(
#                     status=200,
#                     body=json.dumps({
#                         "messages": [{"id": "WA123"}],
#                         "meta": {"api_status": "stable"}
#                     })
#                 )
#             )
#         )
#
#         # Firebase stub
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.POST,
#                     url_path="/v1/projects/test-project/messages:send"
#                 ),
#                 response=MappingResponse(
#                     status=200,
#                     body=json.dumps({
#                         "name": "projects/test-project/messages/123"
#                     })
#                 )
#             )
#         )
#
#     @classmethod
#     async def _create_tables(cls):
#         """Create database tables for testing"""
#         from app.models.db.message_models import Base
#         from app.models.db.dlq_models import Base as DLQBase
#         from sqlalchemy.ext.asyncio import create_async_engine
#
#         engine = create_async_engine(cls.db_url)
#         async with engine.begin() as conn:
#             await conn.run_sync(Base.metadata.create_all)
#             await conn.run_sync(DLQBase.metadata.create_all)
#         await engine.dispose()
#
#     async def asyncSetUp(self):
#         # Clear database before each test
#         async with async_session(self.db_url)() as session:
#             await session.execute("TRUNCATE TABLE messages CASCADE")
#             await session.execute("TRUNCATE TABLE dlq_entries CASCADE")
#             await session.commit()
#
#     # Test Cases
#     async def test_send_sms_message(self):
#         """Test sending an SMS message through the service"""
#         request = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             template_name="welcome",
#             context={"name": "John"}
#         )
#
#         response = await self.service.send_message(request)
#
#         # Verify response
#         self.assertEqual(response.channel, MessageChannel.SMS)
#         self.assertEqual(response.status, MessageStatus.SENT)
#         self.assertIsNotNone(response.message_id)
#
#         # Verify database record
#         message = await self.message_repo.get_by_id(response.message_id)
#         self.assertEqual(message.recipient, "+1234567890")
#         self.assertEqual(message.provider, "twilio_sms")
#
#     async def test_send_whatsapp_template_message(self):
#         """Test sending a WhatsApp template message"""
#         request = WhatsAppMessageRequest(
#             recipient="1234567890",
#             message_type="template",
#             template_name="order_confirmation",
#             language_code="en_US",
#             components=[
#                 {"type": "body", "parameters": ["ORD-12345"]}
#             ]
#         )
#
#         response = await self.service.send_whatsapp_message(request)
#
#         self.assertEqual(response.channel, MessageChannel.WHATSAPP)
#         self.assertEqual(response.status, MessageStatus.SENT)
#         self.assertIsNotNone(response.message_id)
#
#     async def test_send_whatsapp_media_message(self):
#         """Test sending a WhatsApp media message"""
#         media = WhatsAppMedia(
#             link="https://example.com/image.jpg",
#             caption="Product image"
#         )
#
#         response = await self.service.send_whatsapp_media(
#             recipient="1234567890",
#             media=media,
#             media_type="image"
#         )
#
#         self.assertEqual(response.channel, MessageChannel.WHATSAPP)
#         self.assertEqual(response.status, MessageStatus.SENT)
#         self.assertEqual(response.provider, "whatsapp_business")
#
#     async def test_send_whatsapp_interactive_message(self):
#         """Test sending a WhatsApp interactive message"""
#         interactive = WhatsAppInteractive(
#             type="button",
#             body={"text": "Please choose an option"},
#             action={
#                 "buttons": [
#                     {
#                         "type": "reply",
#                         "title": "Option 1",
#                         "payload": "opt1"
#                     }
#                 ]
#             }
#         )
#
#         response = await self.service.send_whatsapp_interactive(
#             recipient="1234567890",
#             interactive=interactive
#         )
#
#         self.assertEqual(response.channel, MessageChannel.WHATSAPP)
#         self.assertEqual(response.status, MessageStatus.SENT)
#
#     async def test_send_push_notification(self):
#         """Test sending a push notification"""
#         request = PushNotificationRequest(
#             recipient=PushNotificationRecipient(
#                 device_tokens=["device_token_123"],
#                 platform="ios"
#             ),
#             payload=PushNotificationPayload(
#                 title="New Message",
#                 body="You have a new notification"
#             )
#         )
#
#         response = await self.service.send_push_notification(
#             recipient=request.recipient,
#             payload=request.payload
#         )
#
#         self.assertEqual(response.channel, MessageChannel.PUSH)
#         self.assertEqual(response.status, MessageStatus.SENT)
#         self.assertEqual(response.provider, "firebase_push")
#
#     async def test_bulk_sms_messages(self):
#         """Test sending SMS messages in bulk"""
#         requests = [
#             MessageRequest(
#                 channel=MessageChannel.SMS,
#                 recipient=f"+12345678{i:02d}",
#                 text=f"Test message {i}"
#             )
#             for i in range(10)
#         ]
#
#         response = await self.service.send_bulk_messages(requests)
#
#         self.assertEqual(response.request_count, 10)
#         self.assertEqual(response.success_count, 10)
#         self.assertEqual(response.failure_count, 0)
#
#         # Verify all messages were persisted
#         messages = await self.message_repo.get_all()
#         self.assertEqual(len(messages), 10)
#
#     async def test_message_retry_on_failure(self):
#         """Test message retry when provider fails"""
#         # Setup WireMock to fail first attempt
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.POST,
#                     url_path="/api/sms/send"
#                 ),
#                 response=MappingResponse(
#                     status=500,
#                     body="Server Error"
#                 ),
#                 priority=1
#             )
#         )
#
#         request = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             text="Test retry"
#         )
#
#         response = await self.service.send_message(request)
#
#         # Should succeed after retry
#         self.assertEqual(response.status, MessageStatus.SENT)
#
#         # Verify two attempts were made (1 failure + 1 success)
#         messages = await self.message_repo.get_all()
#         self.assertEqual(len(messages), 1)
#         self.assertTrue("retry" in messages[0].metadata)
#
#     async def test_dlq_handling(self):
#         """Test failed messages are added to DLQ"""
#         # Setup WireMock to always fail
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.POST,
#                     url_path="/api/sms/send"
#                 ),
#                 response=MappingResponse(
#                     status=500,
#                     body="Server Error"
#                 ),
#                 persistent=True
#             )
#         )
#
#         request = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             text="Test DLQ"
#         )
#
#         with self.assertRaises(MessageSendError):
#             await self.service.send_message(request)
#
#         # Verify message is in DLQ
#         dlq_entries = await self.dlq_repo.get_ready_for_retry(
#             max_retries=3,
#             before=datetime.now()
#         )
#         self.assertEqual(len(dlq_entries), 1)
#         self.assertEqual(dlq_entries[0]["original_message"]["recipient"], "+1234567890")
#
#     async def test_dlq_retry_processing(self):
#         """Test processing messages from DLQ"""
#         # Add a message to DLQ
#         message = Message(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             content={"text": "DLQ test"},
#             status=MessageStatus.FAILED,
#             error="Test error"
#         )
#         await self.message_repo.create(message)
#         await self.dlq_repo.create({
#             "original_message": message.model_dump(),
#             "error": "Test error",
#             "attempts": 0,
#             "next_retry_at": datetime.now(),
#             "status": "pending"
#         })
#
#         # Process DLQ (WireMock is configured to succeed by default)
#         result = await self.service.process_dlq_retries()
#
#         self.assertEqual(result["processed"], 1)
#         self.assertEqual(result["permanent_failures"], 0)
#
#         # Verify message status was updated
#         updated_message = await self.message_repo.get_by_id(message.id)
#         self.assertEqual(updated_message.status, MessageStatus.SENT)
#
#     async def test_rate_limiting(self):
#         """Test rate limiting enforcement"""
#         # Setup rate limiter with very low limits
#         self.service.rate_limiter = RateLimiter(default_limits={"sms": {"limit": 1, "window": 60}})
#
#         # First request should succeed
#         request1 = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             text="Test 1"
#         )
#         await self.service.send_message(request1)
#
#         # Second request should fail
#         request2 = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567891",
#             text="Test 2"
#         )
#         with self.assertRaises(RateLimitExceeded):
#             await self.service.send_message(request2)
#
#     async def test_message_status_check(self):
#         """Test checking message status with provider sync"""
#         # First send a message
#         request = MessageRequest(
#             channel=MessageChannel.SMS,
#             recipient="+1234567890",
#             text="Status check"
#         )
#         send_response = await self.service.send_message(request)
#
#         # Setup WireMock for status check
#         Mappings.create_mapping(
#             mapping=Mapping(
#                 request=MappingRequest(
#                     method=HttpMethods.GET,
#                     url_path=f"/api/messages/{send_response.message_id}"
#                 ),
#                 response=MappingResponse(
#                     status=200,
#                     body=json.dumps({
#                         "status": "delivered"
#                     })
#                 )
#             )
#         )
#
#         # Check status
#         status_response = await self.service.get_message_status(send_response.message_id)
#         self.assertEqual(status_response.status, "delivered")
