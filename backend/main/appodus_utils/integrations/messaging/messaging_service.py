# import asyncio
# import json
# import logging
# from concurrent.futures import ThreadPoolExecutor
# from datetime import datetime
# from typing import List, Dict, Optional, Callable
#
# # Repositories
# from pydantic import ValidationError
# from pywebpush import WebPushException, webpush
#
# from main.app.config.settings import settings
# from main.app.domain.message.models import QueryMessageDto
# from main.app.domain.message.service import MessageService
# # Exceptions
# from main.appodus_utils.integrations.exception.exceptions import (
#     IntegrationException,
#     IntegrationValidationException, IntegrationFatalException
# )
# from main.appodus_utils.integrations.messaging.models import MessageRequest, MessageResponse, Message, MessageChannel, \
#     MessageStatus
# from main.appodus_utils.integrations.messaging.providers.push.models import PushNotificationRecipient, PushNotificationPayload, \
#     WebPushNotificationRecipient, WebPushNotificationPayload
# from main.appodus_utils.integrations.messaging.providers.whatsapp.models import WhatsAppMessageRequest, WhatsAppMedia, \
#     WhatsAppInteractive
# from main.appodus_utils.integrations.messaging.router import MessageRouter
# from main.appodus_utils.integrations.messaging.services.bulk_processing.models import BulkWhatsAppMessageRequest, \
#     BulkWhatsAppMediaRequest, BulkWhatsAppInteractiveRequest, BulkPushNotificationRequest, \
#     BulkWebPushNotificationRequest, BulkMessageResponse
# from main.appodus_utils.integrations.messaging.services.bulk_processing.processor import BulkProcessor
# from main.appodus_utils.integrations.messaging.services.cost_tracking import cost_tracker
# from main.appodus_utils.integrations.messaging.services.dead_letter_queue.dlq import DeadLetterQueue
# from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
# from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter, Throttler, RateLimitExceeded
# from main.appodus_utils.integrations.messaging.services.validation import ValidatedMessage, MessageValidator
# from main.appodus_utils.integrations.messaging.templating.service import TemplateService
#
# # logger = logging.getLogger(__name__)
#
#
# class MessagingService:
#     """
#     Complete messaging service handling all channels with:
#     - Individual and bulk messaging
#     - Retry and circuit breaking
#     - Rate limiting and throttling
#     - Dead letter queue
#     - Cost tracking
#     - Full observability
#     """
#
#     def __init__(
#             self,
#             router: 'MessageRouter',
#             template_service: TemplateService,
#             message_service: MessageService,
#             dlq: DeadLetterQueue,
#             max_concurrency: int = 10,
#             bulk_batch_size: int = 50
#     ):
#         self.router = router
#         self.template_service = template_service
#         self.message_service = message_service
#         self.dlq = dlq
#         self.bulk_processor = BulkProcessor(
#             max_concurrency=max_concurrency,
#             batch_size=bulk_batch_size
#         )
#         self.rate_limiter = RateLimiter()
#         self.throttler = Throttler(rps_limit=20)
#         self.executor = ThreadPoolExecutor(max_workers=max_concurrency)
#         self._init_metrics()
#
#     @staticmethod
#     def _init_metrics():
#         """Initialize all metrics collectors"""
#         metrics_manager.register_gauge(
#             'messaging_active_tasks',
#             'Current active messaging tasks',
#             ['channel']
#         )
#         metrics_manager.register_counter(
#             'message_attempts',
#             'Message send attempts',
#             ['channel', 'provider', 'status']
#         )
#         metrics_manager.register_histogram(
#             'message_processing_time',
#             'Time to process messages',
#             ['channel', 'provider']
#         )
#
#     # Core Message Sending
#     async def send_message(self, request: MessageRequest) -> MessageResponse:
#         """
#         Process and send a single message through the complete pipeline:
#         1. Validation
#         2. Rate limiting
#         3. Template rendering
#         4. Provider routing
#         5. Retry on failure
#         6. DLQ on permanent failure
#         """
#         try:
#             # Validate and apply rate limits
#             validated = await self._validate_message(request)
#             await self._check_rate_limits(validated)
#
#             # Create and send message with throttling
#             async with self.throttler:
#                 message = await self._create_message_record(validated)
#                 sent_message = await self._send_with_retry(message)
#
#                 # Track cost
#                 cost = cost_tracker.calculate_cost(
#                     sent_message.provider,
#                     sent_message.channel,
#                     {
#                         'recipient': sent_message.recipient,
#                         'length': len(sent_message.content.get('text', ''))
#                     }
#                 )
#                 cost_tracker.record_cost(sent_message, cost)
#
#                 return MessageResponse.from_message(sent_message)
#
#         except RateLimitExceeded as e:
#             logger.warning(f"Rate limit exceeded: {str(e)}")
#             raise e
#         except ValidationError as e:
#             logger.error(f"Validation failed: {str(e)}")
#             raise IntegrationValidationException(f"Invalid message: {str(e)}")
#         except Exception as e:
#             logger.error(f"Message processing failed: {str(e)}", exc_info=True)
#             raise IntegrationException(f"Failed to send message: {str(e)}")
#
#     # WhatsApp Operations
#     async def send_whatsapp_message(self, request: WhatsAppMessageRequest) -> MessageResponse:
#         """Send WhatsApp text or template message with media support"""
#         try:
#             self._validate_whatsapp_recipient(request.recipient)
#
#             message = Message(
#                 channel=MessageChannel.WHATSAPP,
#                 recipient=request.recipient,
#                 content={
#                     'message_type': request.message_type,
#                     'text': request.text,
#                     'template_name': request.template_name,
#                     'language_code': request.language_code,
#                     'components': request.components
#                 },
#                 status=MessageStatus.PENDING,
#                 metadata=request.metadata or {}
#             )
#
#             sent_message = await self._send_with_retry(message)
#             return MessageResponse.from_message(sent_message)
#
#         except Exception as e:
#             await self._handle_failure(message, e)
#             raise IntegrationException(f"WhatsApp send failed: {str(e)}")
#
#     async def send_whatsapp_media(
#             self,
#             recipient: str,
#             media: WhatsAppMedia,
#             media_type: str = 'image',
#             caption: Optional[str] = None,
#             metadata: Optional[Dict] = None
#     ) -> MessageResponse:
#         """Send media through WhatsApp (image/document/video/audio)"""
#         try:
#             self._validate_whatsapp_recipient(recipient)
#             self._validate_media_type(media_type)
#
#             message = Message(
#                 channel=MessageChannel.WHATSAPP,
#                 recipient=recipient,
#                 content={
#                     'message_type': media_type,
#                     'media': {
#                         'link': media.link,
#                         'id': media.id,
#                         'caption': caption or media.caption,
#                         'filename': media.filename
#                     }
#                 },
#                 status=MessageStatus.PENDING,
#                 metadata=metadata or {}
#             )
#
#             sent_message = await self._send_with_retry(message)
#             return MessageResponse.from_message(sent_message)
#
#         except Exception as e:
#             await self._handle_failure(message, e)
#             raise IntegrationException(f"WhatsApp media send failed: {str(e)}")
#
#     async def send_whatsapp_interactive(
#             self,
#             recipient: str,
#             interactive: WhatsAppInteractive,
#             metadata: Optional[Dict] = None
#     ) -> MessageResponse:
#         """Send interactive WhatsApp message (buttons/lists/products)"""
#         try:
#             self._validate_whatsapp_recipient(recipient)
#             self._validate_interactive(interactive)
#
#             message = Message(
#                 channel=MessageChannel.WHATSAPP,
#                 recipient=recipient,
#                 content={
#                     'message_type': 'interactive',
#                     'interactive': interactive.model_dump()
#                 },
#                 status=MessageStatus.PENDING,
#                 metadata=metadata or {}
#             )
#
#             sent_message = await self._send_with_retry(message)
#             return MessageResponse.from_message(sent_message)
#
#         except Exception as e:
#             await self._handle_failure(message, e)
#             raise IntegrationException(f"WhatsApp interactive send failed: {str(e)}")
#
#     # Push Notification Operations
#     async def send_push_notification(
#             self,
#             recipient: PushNotificationRecipient,
#             payload: PushNotificationPayload,
#             metadata: Optional[Dict] = None
#     ) -> MessageResponse:
#         """Send mobile push notification (iOS/Android)"""
#         try:
#             message = Message(
#                 channel=MessageChannel.PUSH,
#                 recipient=recipient.device_tokens[0],
#                 content={
#                     'payload': payload.model_dump(),
#                     'recipient': recipient.model_dump()
#                 },
#                 status=MessageStatus.PENDING,
#                 metadata=metadata or {}
#             )
#
#             sent_message = await self._send_with_retry(message)
#             return MessageResponse.from_message(sent_message)
#
#         except Exception as e:
#             await self._handle_failure(message, e)
#             raise IntegrationException(f"Push notification failed: {str(e)}")
#
#     async def send_web_push(
#             self,
#             recipient: WebPushNotificationRecipient,
#             payload: WebPushNotificationPayload,
#             metadata: Optional[Dict] = None
#     ) -> MessageResponse:
#         """
#         Send web push notification using VAPID
#         """
#         try:
#             # Validate recipient
#             if not all(key in recipient.keys for key in ['auth', 'p256dh']):
#                 raise IntegrationValidationException("Web push recipient missing required keys")
#
#             # Create message record
#             message = Message(
#                 channel=MessageChannel.WEB_PUSH,
#                 recipient=recipient.endpoint,
#                 content={
#                     "payload": payload.model_dump(),
#                     "recipient": recipient.model_dump()
#                 },
#                 status=MessageStatus.PENDING,
#                 metadata=metadata or {}
#             )
#
#             # Send with retry
#             sent_message = await self._send_with_retry(message)
#             return MessageResponse.from_message(sent_message)
#
#         except Exception as e:
#             await self._handle_failure(message, e)
#             raise IntegrationException(f"Web push failed: {str(e)}")
#
#     # Bulk Operations
#     async def send_bulk_messages(self, requests: List[MessageRequest]) -> BulkMessageResponse:
#         """Process messages in bulk with parallel execution"""
#         return await self._process_bulk(
#             requests,
#             lambda req: self.send_message(req)
#         )
#
#     async def send_bulk_whatsapp_messages(
#             self,
#             request: BulkWhatsAppMessageRequest
#     ) -> BulkMessageResponse:
#         """Send WhatsApp messages in bulk (text/template)"""
#         return await self._process_bulk(
#             request.requests,
#             lambda req: self.send_whatsapp_message(req),
#             request.metadata
#         )
#
#     async def send_bulk_whatsapp_media(
#             self,
#             request: BulkWhatsAppMediaRequest
#     ) -> BulkMessageResponse:
#         """Send WhatsApp media messages in bulk"""
#         return await self._process_bulk_dicts(
#             request.requests,
#             lambda req: self.send_whatsapp_media(
#                 recipient=req['recipient'],
#                 media=req['media'],
#                 media_type=req.get('media_type', 'image'),
#                 caption=req.get('caption'),
#                 metadata=request.metadata or req.get('metadata', {})
#             )
#         )
#
#     async def send_bulk_whatsapp_interactive(
#             self,
#             request: BulkWhatsAppInteractiveRequest
#     ) -> BulkMessageResponse:
#         """Send WhatsApp interactive messages in bulk"""
#         return await self._process_bulk_dicts(
#             request.requests,
#             lambda req: self.send_whatsapp_interactive(
#                 recipient=req['recipient'],
#                 interactive=req['interactive'],
#                 metadata=request.metadata or req.get('metadata', {})
#             )
#         )
#
#     async def send_bulk_push_notifications(
#             self,
#             request: BulkPushNotificationRequest
#     ) -> BulkMessageResponse:
#         """Send push notifications in bulk"""
#         return await self._process_bulk(
#             request.requests,
#             lambda req: self.send_push_notification(
#                 recipient=req.recipient,
#                 payload=req.payload,
#                 metadata=request.metadata or {}
#             )
#         )
#
#     async def send_bulk_web_push(
#             self,
#             request: BulkWebPushNotificationRequest
#     ) -> BulkMessageResponse:
#         """
#         Send web push notifications in bulk
#         """
#         start_time = datetime.now()
#
#         async def process_one(push_request: Dict):
#             return await self.send_web_push(
#                 recipient=WebPushNotificationRecipient(**push_request['recipient']),
#                 payload=WebPushNotificationPayload(**push_request['payload']),
#                 metadata=request.metadata or push_request.get('metadata', {})
#             )
#
#         results = await self.bulk_processor.process_with_retry(
#             request.requests,
#             process_one,
#             max_retries=2
#         )
#
#         return BulkMessageResponse(
#             request_count=len(request.requests),
#             success_count=len(results.successes),
#             failure_count=len(results.failures),
#             processing_time=(datetime.now() - start_time).total_seconds(),
#             successes=results.successes,
#             failures=results.failures
#         )
#
#     # DLQ Management
#     async def process_dlq_retries(self, max_batch_size: int = 100) -> Dict:
#         """Process messages in DLQ that are ready for retry"""
#         return await self.dlq.process_retries(max_batch_size)
#
#     # Message Status
#     async def get_message_status(self, message_id: str) -> MessageResponse:
#         """Get current message status with provider sync"""
#         message = await self.message_service.get_message_by_id(message_id)
#
#         if message.status == MessageStatus.PENDING and message.provider:
#             provider_status = await self.router.get_message_status(
#                 message.provider,
#                 message.external_id
#             )
#             if provider_status and provider_status != message.status:
#                 await self.message_service.update_message_status(message.id, provider_status)
#
#         return MessageResponse.from_message(message)
#
#     # Internal Processing Methods
#     async def _process_bulk(
#             self,
#             requests: List,
#             process_fn: Callable,
#             shared_metadata: Optional[Dict] = None
#     ) -> BulkMessageResponse:
#         """Generic bulk processing with metrics"""
#         start_time = datetime.now()
#
#         results = await self.bulk_processor.process_with_retry(
#             requests,
#             process_fn,
#             max_retries=2
#         )
#
#         return BulkMessageResponse(
#             request_count=len(requests),
#             success_count=len(results.successes),
#             failure_count=len(results.failures),
#             processing_time=(datetime.now() - start_time).total_seconds(),
#             successes=results.successes,
#             failures=results.failures
#         )
#
#     async def _process_bulk_dicts(
#             self,
#             requests: List[Dict],
#             process_fn: Callable,
#             shared_metadata: Optional[Dict] = None
#     ) -> BulkMessageResponse:
#         """Bulk processing for dictionary-based requests"""
#         start_time = datetime.now()
#
#         # Apply shared metadata if provided
#         processed_requests = requests
#         if shared_metadata:
#             processed_requests = [
#                 {**req, 'metadata': {**req.get('metadata', {}), **shared_metadata}}
#                 for req in requests
#             ]
#
#         results = await self.bulk_processor.process_with_retry(
#             processed_requests,
#             process_fn,
#             max_retries=2
#         )
#
#         return BulkMessageResponse(
#             request_count=len(requests),
#             success_count=len(results.successes),
#             failure_count=len(results.failures),
#             processing_time=(datetime.now() - start_time).total_seconds(),
#             successes=results.successes,
#             failures=results.failures
#         )
#
#     async def _validate_message(self, request: MessageRequest) -> ValidatedMessage:
#         """Validate and sanitize message request"""
#         validated = ValidatedMessage(
#             channel=request.channel,
#             recipient=request.recipient,
#             template_name=request.template_name,
#             context=request.context,
#             priority=request.priority,
#             metadata=request.metadata or {}
#         )
#
#         if not MessageValidator.validate_recipient(validated.channel, validated.recipient):
#             raise IntegrationValidationException(f"Invalid recipient for channel {validated.channel}")
#
#         return validated
#
#     async def _check_rate_limits(self, message: ValidatedMessage):
#         """Apply rate limiting based on tenant and channel"""
#         tenant = message.metadata.get("tenant", "default")
#         await self.rate_limiter.check_limit(
#             f"{message.channel}:{tenant}"
#         )
#
#     async def _create_message_record(self, validated: ValidatedMessage) -> Message:
#         """Create message record with rendered content"""
#         content = await self._render_content(validated)
#
#         return Message(
#             channel=validated.channel,
#             recipient=validated.recipient,
#             content=content,
#             status=MessageStatus.PENDING,
#             priority=validated.priority,
#             metadata=validated.metadata
#         )
#
#     async def _render_content(self, validated: ValidatedMessage) -> Dict:
#         """Render message content from template"""
#         if validated.template_name:
#             rendered = await self.template_service.render_message(
#                 channel=validated.channel,
#                 template_name=validated.template_name,
#                 context=validated.context
#             )
#             return {"text": rendered, **validated.metadata}
#         return {"text": validated.context.get("text", ""), **validated.metadata}
#
#     async def _send_with_retry(self, message: Message, max_retries: int = 2) -> Message:
#         """Send message with retry logic and circuit breaking"""
#         last_error = None
#
#         for attempt in range(max_retries + 1):
#             try:
#                 # Track active task
#                 metrics_manager.messaging_active_tasks.labels(
#                     channel=message.channel
#                 ).inc()
#
#                 start_time = datetime.now()
#                 if message.channel == MessageChannel.WEB_PUSH:
#                     result = await self._send_web_push_direct(message)
#                 else:
#                     result = await self.router.send_message(message)
#                 processing_time = (datetime.now() - start_time).total_seconds()
#
#                 # Track success
#                 metrics_manager.track_message(
#                     channel=message.channel,
#                     provider=result.provider or "unknown",
#                     status="success",
#                     duration=processing_time
#                 )
#
#                 await self.message_service.update(result)
#                 return result
#
#             except Exception as e:
#                 last_error = e
#                 logger.warning(
#                     f"Attempt {attempt + 1} failed for message {message.id}: {str(e)}"
#                 )
#
#                 # Track failure
#                 metrics_manager.track_message(
#                     channel=message.channel,
#                     provider=message.provider or "unknown",
#                     status="failed",
#                     error_type=e.__class__.__name__
#                 )
#
#                 if attempt < max_retries:
#                     await asyncio.sleep(2 ** attempt)  # Exponential backoff
#
#             finally:
#                 metrics_manager.messaging_active_tasks.labels(
#                     channel=message.channel
#                 ).dec()
#
#         # All retries failed
#         await self._handle_failure(message, last_error)
#         raise IntegrationFatalException(f"All retries failed: {str(last_error)}")
#
#     async def _send_web_push_direct(self, message: Message) -> Message:
#         """
#         Direct web push sending (bypasses provider routing)
#         """
#         try:
#             content = message.content
#             recipient = WebPushNotificationRecipient(**content['recipient'])
#             payload = content['payload']
#
#             # Get VAPID settings from config
#             vapid_private_key = settings.WEB_PUSH_PRIVATE_KEY
#             vapid_claims = {
#                 "sub": f"mailto:{settings.WEB_PUSH_SUBJECT_EMAIL}"
#             }
#
#             # Send the web push
#             response = webpush(
#                 subscription_info={
#                     "endpoint": recipient.endpoint,
#                     "keys": recipient.keys
#                 },
#                 data=json.dumps(payload),
#                 vapid_private_key=vapid_private_key,
#                 vapid_claims=vapid_claims
#             )
#
#             message.status = MessageStatus.SENT
#             message.provider = "web_push"
#             message.provider_id = response.headers.get('Location', '')
#             return message
#
#         except WebPushException as e:
#             if e.response.status_code == 410:
#                 message.error = "Subscription expired"
#             else:
#                 message.error = str(e)
#             raise
#
#     async def _handle_failure(self, message: QueryMessageDto, error: Exception):
#         """Handle message failure including DLQ registration"""
#         error_msg = f"{error.__class__.__name__}: {str(error)}"
#         message.status = MessageStatus.FAILED
#         message.error = error_msg[:500]  # Truncate long errors
#
#         try:
#             await self.message_service.update_message_status(message.id, message.status, message.error)
#             await self.dlq.add_to_dlq(
#                 message,
#                 error_msg,
#                 metadata={
#                     "process_fn": self.router.send_message,
#                     "trace_id": message.metadata.get("trace_id")
#                 }
#             )
#             logger.info(f"Message {message.id} added to DLQ")
#         except Exception as dlq_error:
#             logger.error(
#                 f"Failed to handle message failure {message.id}: {str(dlq_error)}",
#                 exc_info=True
#             )
#
#     # Validation Helpers
#     @staticmethod
#     def _validate_whatsapp_recipient(recipient: str):
#         if not MessageValidator.validate_recipient(MessageChannel.WHATSAPP, recipient):
#             raise IntegrationValidationException("Invalid WhatsApp recipient format")
#
#     @staticmethod
#     def _validate_media_type(media_type: str):
#         if media_type not in ['image', 'document', 'video', 'audio']:
#             raise IntegrationValidationException(f"Invalid media type: {media_type}")
#
#     @staticmethod
#     def _validate_interactive(interactive: WhatsAppInteractive):
#         if interactive.type not in ['button', 'list', 'product', 'product_list']:
#             raise IntegrationValidationException(f"Invalid interactive type: {interactive.type}")
#
#         if interactive.type == 'button' and not interactive.action.buttons:
#             raise IntegrationValidationException("Button interactive requires buttons")
#
#         if interactive.type == 'list' and not interactive.action.sections:
#             raise IntegrationValidationException("List interactive requires sections")
