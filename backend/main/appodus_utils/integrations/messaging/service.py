# import asyncio
# import logging
# import mimetypes
# from typing import List, Dict, Optional
#
# from fastapi.encoders import jsonable_encoder
# from kink import inject, di
#
# from main.app.domain.message.models import UpsertMessageDto
# from main.app.domain.message.service import MessageService
# from main.appodus_utils.integrations.exception.exceptions import (
#     IntegrationException,
#     IntegrationValidationException,
#     IntegrationRateLimitException
# )
# from main.appodus_utils.integrations.messaging.models import (
#     MessageRequest,
#     SmsPayload,
#     WhatsappPayload,
#     MessageChannel, EmailPayloadRequest, EmailPayload, AttachmentRequest, Attachment
# )
# from main.appodus_utils.integrations.messaging.models import MessageStatus
# from main.appodus_utils.integrations.messaging.router import MessageRouter
# from main.appodus_utils.integrations.messaging.services.bulk_processing.processor import BulkProcessor
# from main.appodus_utils.integrations.messaging.services.dead_letter_queue.dlq import DeadLetterQueue
# from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
# from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter, Throttler
# from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager
# from main.appodus_utils.integrations.messaging.templating.service import TemplateService
# from main.appodus_utils import Utils, Base64Utils
#
# logger: logging.Logger = di['logger']
#
#
# @inject
# class MessagingService:
#     def __init__(
#             self,
#             router: MessageRouter,
#             template_service: TemplateService,
#             message_service: MessageService,
#             dlq: DeadLetterQueue,
#             rate_limiter: RateLimiter
#     ):
#         self.MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB max per attachment
#         self.router = router
#         self.template_service = template_service
#         self.message_service = message_service
#         self.dlq = dlq
#         self.bulk_processor = BulkProcessor(
#             max_concurrency=10,
#             batch_size=50
#         )
#         self.rate_limiter = rate_limiter
#         self.throttler = Throttler(rps_limit=20)
#         self._init_metrics()
#
#     @staticmethod
#     def _init_metrics():
#         pass
#         # metrics_manager.register_gauge(
#         #     'messaging_active_tasks',
#         #     'Current active messaging tasks',
#         #     ['channel']
#         # )
#         # metrics_manager.register_counter(
#         #     'message_attempts',
#         #     'Message send attempts',
#         #     ['channel', 'provider', 'status']
#         # )
#         # metrics_manager.register_histogram(
#         #     'message_processing_time',
#         #     'Time to process messages',
#         #     ['channel', 'provider']
#         # )
#
#     @resilience_manager.messaging_circuit_breaker(name="send_message")
#     async def send_message(self, request: MessageRequest) -> UpsertMessageDto:
#         """
#         Process and send a message using the unified request model
#         """
#         try:
#             # Validate and convert to internal message format
#             message = await self._convert_request(request)
#
#             # Apply rate limiting
#             await self._check_rate_limits(message)
#
#             # Process with throttling
#             async with self.throttler:
#                 sent_message = await self._send_with_retry(message)
#
#             return sent_message
#
#         except IntegrationRateLimitException as e:
#             logger.warning(f"{str(e)}")
#             raise e
#         except IntegrationValidationException as e:
#             logger.error(f"Invalid message: {str(e)}")
#             raise e
#         except Exception as e:
#             logger.error(f"Failed to send message: {str(e)}", exc_info=True)
#             raise IntegrationException(f"Failed to send message: {str(e)}")
#
#     async def send_bulk(self, requests: List[MessageRequest]) -> Dict:
#         """
#         Process bulk messages with parallel execution
#         """
#
#         # start_time = Utils.datetime_now()
#
#         async def process_one(req: MessageRequest):
#             try:
#                 message = await self._convert_request(req)
#                 sent_message = await self._send_with_retry(message)
#                 return True, sent_message
#             except Exception as e:
#                 return False, str(e)
#
#         results = await self.bulk_processor.process_with_retry(
#             requests,
#             process_one,
#             max_retries=2
#         )
#
#         return {
#             "total": len(requests),
#             "success": len(results.successes),
#             "failures": len(results.failures),
#             "processing_time": results.processing_time,
#             "results": results
#         }
#
#     async def _convert_request(self, request: MessageRequest) -> UpsertMessageDto:
#         """
#         Convert unified request to internal UpsertMessageDto format
#         """
#         base_message = {
#             "channel": request.channel.value,
#             "to": request.to,
#             "scheduled_at": request.schedule_at,
#             "priority": request.priority,
#             "status": MessageStatus.PENDING,
#             "extras": request.extras or {}
#         }
#
#         if request.channel == MessageChannel.EMAIL:
#             return await self._convert_email_request(base_message, request)
#         elif request.channel == MessageChannel.SMS:
#             return await self._convert_sms_request(base_message, request)
#         elif request.channel == MessageChannel.WHATSAPP:
#             return await self._convert_whatsapp_request(base_message, request)
#         elif request.channel in (MessageChannel.PUSH, MessageChannel.WEB_PUSH):
#             return await self._convert_push_request(base_message, request)
#         else:
#             raise IntegrationValidationException(f"Unsupported channel: {request.channel}")
#
#     async def _convert_email_request(self, message: Dict, request: MessageRequest) -> UpsertMessageDto:
#         """Convert EmailPayload to internal message format"""
#         payload: EmailPayloadRequest = request.payload
#
#         if not payload.text and not payload.html and request.template:
#             template_content = await self._render_template(request)
#             payload.html = template_content
#
#         if payload.attachments:
#             payload.attachments = self._attach_attachments(payload.attachments)
#
#         attachments = payload.attachments
#         payload.attachments = None
#         payload_data = jsonable_encoder(payload, by_alias=False)
#         email_payload = EmailPayload(**payload_data)
#
#         message["payload"] = email_payload
#         response = UpsertMessageDto(**message)
#         response.payload.attachments = attachments
#
#         return response
#
#     async def _convert_sms_request(self, message: Dict, request: MessageRequest) -> UpsertMessageDto:
#         """Convert SmsPayload to internal message format"""
#         payload: SmsPayload = request.payload
#
#         if not payload.text and request.template:
#             template_content = await self._render_template(request)
#             payload.text = template_content
#
#         message["payload"] = payload
#
#         return UpsertMessageDto(**message)
#
#     async def _convert_whatsapp_request(self, message: Dict, request: MessageRequest) -> UpsertMessageDto:
#         """Convert WhatsappPayload to internal message format"""
#         payload: WhatsappPayload = request.payload
#
#         if not payload.text and request.template:
#             template_content = await self._render_template(request)
#             payload.text = template_content
#
#         message["payload"] = payload
#
#         return UpsertMessageDto(**message)
#
#     @staticmethod
#     async def _convert_push_request(message: Dict, request: MessageRequest) -> UpsertMessageDto:
#         """Convert push payloads to internal message format"""
#         message["payload"] = request.payload
#
#         return UpsertMessageDto(**message)
#
#     async def _render_template(self, request: MessageRequest) -> Optional[str]:
#         """Render message content from template"""
#         if request.template:
#             rendered = await self.template_service.render_message(
#                 channel=request.channel,
#                 template_name=request.template,
#                 context=request.template_variables
#             )
#             return rendered
#         return None
#
#     async def _check_rate_limits(self, message: UpsertMessageDto):
#         """Apply rate limiting based on tenant and channel"""
#         tenant = message.extras.get("tenant", "default")
#         await self.rate_limiter.check_limit(
#             f"{message.channel.value}:{tenant}"
#         )
#
#     async def _send_with_retry(self, message: UpsertMessageDto, max_retries: int = 2) -> UpsertMessageDto:
#         """Send message with retry logic"""
#         last_error = None
#         start_time = None
#         for attempt in range(max_retries + 1):
#             try:
#                 # TODO: fix
#                 # metrics_manager.messaging_active_tasks.labels(
#                 #     channel=message.channel
#                 # ).inc()
#
#                 start_time = Utils.datetime_now()
#                 result = await self.router.send_message(message)
#                 processing_time = Utils.datetime_now_diff_in_sec(start_time)
#
#                 metrics_manager.track_message(
#                     channel=message.channel.value,
#                     provider=result.provider or "unknown",
#                     status="success",
#                     duration=processing_time
#                 )
#
#                 await self.message_service.update_message_sent(message.id, Utils.datetime_now(), result)
#                 return result
#
#             except Exception as e:
#
#                 processing_time = Utils.datetime_now_diff_in_sec(start_time)
#                 last_error = e
#                 logger.warning(
#                     f"Attempt {attempt + 1} failed for message {message.id}: {str(e)}"
#                 )
#
#                 metrics_manager.track_message(
#                     channel=message.channel.value,
#                     provider=message.provider or "unknown",
#                     status="failed",
#                     duration=processing_time
#                 )
#
#                 if attempt < max_retries:
#                     await asyncio.sleep(2 ** attempt)  # Exponential backoff
#
#             finally:
#                 pass
#                 # TODO: fix
#                 # metrics_manager.messaging_active_tasks.labels(
#                 #     channel=message.channel
#                 # ).dec()
#
#         await self._handle_failure(message, last_error)
#         raise IntegrationException(f"All retries failed: {str(last_error)}")
#
#     def attach_attachments(self, payloads: List[AttachmentRequest]) -> Optional[List[Attachment]]:
#         attachments: List[Attachment] = []
#         for payload in payloads:
#             if not payload.file_path.exists():
#                 raise FileNotFoundError(f"File not found: {payload.file_path}")
#
#             # Validate file size
#             Utils.validate_file_size(payload.file_path, self.MAX_ATTACHMENT_SIZE)
#
#             # Encode file
#             encoded_content = Base64Utils.file_path_to_base64(payload.file_path)
#
#             filename = payload.filename or payload.file_path.name
#             guessed_type, _ = mimetypes.guess_type(payload.file_path)
#             content_type = guessed_type or "application/octet-stream"
#
#             attachment = Attachment(
#                 content_type=content_type,
#                 filename=filename,
#                 content=encoded_content,
#             )
#             attachments.append(attachment)
#
#         return attachments
#
#
#     async def _handle_failure(self, message: UpsertMessageDto, error: Exception):
#         """Handle message failure including DLQ registration"""
#         error_msg = f"{error.__class__.__name__}: {str(error)}"
#         message.status = MessageStatus.FAILED
#         message.error = error_msg[:500]  # Truncate long errors
#
#         try:
#
#             await self.message_service.update_message_status(message.id, message.status, message.error)
#             await self.dlq.add_to_dlq(
#                 message,
#                 error_msg,
#                 extras={
#                     "process_fn": self.router.send_message,
#                     "trace_id": message.extras.get("trace_id")
#                 }
#             )
#             logger.info(f"UpsertMessageDto {message.id} added to DLQ")
#         except Exception as dlq_error:
#             logger.error(
#                 f"Failed to handle message failure {message.id}: {str(dlq_error)}",
#                 exc_info=True
#             )
#
#     # DLQ Management
#     async def process_dlq_retries(self, max_batch_size: int = 100) -> Dict:
#         """Process messages in DLQ that are ready for retry"""
#         return await self.dlq.process_retries(max_batch_size)
#
#     # Status Checking
#     async def get_message_status(self, message_id: str) -> UpsertMessageDto:
#         """Get current message status with provider sync"""
#         message = await self.message_service.get_message_by_id(message_id)
#         if not message:
#             raise IntegrationValidationException("Message not found")
#
#         if message.status == "pending" and message.provider:
#             provider_status = await self.router.get_message_status(
#                 message.provider,
#                 message.provider_id
#             )
#             if provider_status and provider_status != message.status:
#                 message.status = provider_status
#                 await self.message_service.update_message_status(message_id, message.status)
#
#         return message


import logging
import mimetypes
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from kink import inject, di

from main.app.domain.message.models import UpsertMessageDto
from main.app.domain.message.service import MessageService
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationException,
    IntegrationValidationException,
    IntegrationRateLimitException,
)
from main.appodus_utils.integrations.messaging.models import (
    Attachment,
    AttachmentRequest,
    EmailPayload,
    EmailPayloadRequest,
    MessageChannel,
    MessageRequest,
    MessageStatus,
    SmsPayload,
    WhatsappPayload,
)
from main.appodus_utils.integrations.messaging.router import MessageRouter
from main.appodus_utils.integrations.messaging.services.bulk_processing.processor import BulkProcessor
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.dlq import DeadLetterQueue
from main.appodus_utils.integrations.messaging.services.metrics import metrics_manager
from main.appodus_utils.integrations.messaging.services.rate_limiting import RateLimiter, Throttler
from main.appodus_utils.integrations.messaging.templating.service import TemplateService
from main.appodus_utils import Base64Utils, Utils

logger: logging.Logger = di['logger']


@inject
class MessagingService:
    def __init__(
            self,
            router: MessageRouter,
            template_service: TemplateService,
            message_service: MessageService,
            dlq: DeadLetterQueue,
            rate_limiter: RateLimiter,
    ):
        self.MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
        self.router = router
        self.template_service = template_service
        self.message_service = message_service
        self.dlq = dlq
        self.bulk_processor = BulkProcessor(max_concurrency=10, batch_size=50)
        self.rate_limiter = rate_limiter
        self.throttler = Throttler(rps_limit=20)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(self, request: MessageRequest) -> UpsertMessageDto:
        """Process and send a message.

        Retry, circuit breaking, and provider fallback are entirely owned by
        MessageRouter. MessagingService owns conversion, rate limiting, metrics,
        and DLQ registration.

        Do NOT add a circuit breaker decorator here: the bare except below
        re-wraps every exception as IntegrationException before it can
        propagate, making any outer circuit breaker permanently blind.
        """
        # Initialise before try so _handle_failure always receives a defined
        # value — avoids fragile runtime variable inspection in the except block.
        # No inline type annotation: annotating a local variable declaration
        # causes PyCharm to treat it as a potentially unbound annotation rather
        # than a guaranteed assignment, producing a false "referenced before
        # assignment" warning in the except block.
        message = None

        try:
            message = await self._convert_request(request)
            await self._check_rate_limits(message)

            async with self.throttler:
                start_time = datetime.now(timezone.utc)
                result = await self.router.send_message(message)

            self._track_success(message, result, start_time)
            await self.message_service.update_message_sent(
                message.id, datetime.now(timezone.utc), result
            )
            return result

        except IntegrationRateLimitException as e:
            # Rate limit violations are not transient — do not DLQ.
            logger.warning("Rate limit hit: %s", e)
            raise

        except IntegrationValidationException as e:
            # Validation errors are not transient — do not DLQ.
            logger.error("Validation error: %s", e)
            raise

        except Exception as e:
            logger.error("Failed to send message: %s", e, exc_info=True)
            await self._handle_failure(message, e)
            raise IntegrationException(f"Failed to send message: {e}") from e

    async def send_bulk(self, requests: List[MessageRequest]) -> Dict:
        """Process bulk messages with parallel execution.

        Rate limiting, throttling, metrics, and DLQ registration are applied
        per message — consistent with the single-send path.
        """
        async def process_one(req: MessageRequest):
            message = None  # see send_message for annotation rationale
            try:
                message = await self._convert_request(req)
                await self._check_rate_limits(message)
                async with self.throttler:
                    start_time = datetime.now(timezone.utc)
                    result = await self.router.send_message(message)
                self._track_success(message, result, start_time)
                return True, result
            except Exception as e:
                await self._handle_failure(message, e)
                return False, str(e)

        results = await self.bulk_processor.process_with_retry(
            requests,
            process_one,
            max_retries=2,
        )

        return {
            "total": len(requests),
            "success": len(results.successes),
            "failures": len(results.failures),
            "processing_time": results.processing_time,
            "results": results,
        }

    async def process_dlq_retries(self, max_batch_size: int = 100) -> Dict:
        """Process messages in the DLQ that are ready for retry."""
        return await self.dlq.process_retries(max_batch_size)

    async def get_message_status(self, message_id: str) -> UpsertMessageDto:
        """Get current message status, syncing from provider if pending."""
        message = await self.message_service.get_message_by_id(message_id)
        if not message:
            raise IntegrationValidationException("Message not found")

        if message.status == "pending" and message.provider:
            provider_status = await self.router.get_message_status(
                message.provider,
                message.provider_id,
            )
            if provider_status and provider_status != message.status:
                message.status = provider_status
                await self.message_service.update_message_status(
                    message_id, message.status
                )

        return message

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    async def _convert_request(self, request: MessageRequest) -> UpsertMessageDto:
        """Convert a unified MessageRequest to the internal UpsertMessageDto."""
        base_message = {
            "channel": request.channel.value,
            "to": request.to,
            "scheduled_at": request.schedule_at,
            "priority": request.priority,
            "status": MessageStatus.PENDING,
            "extras": request.extras or {},
        }

        if request.channel == MessageChannel.EMAIL:
            return await self._convert_email_request(base_message, request)
        elif request.channel == MessageChannel.SMS:
            return await self._convert_sms_request(base_message, request)
        elif request.channel == MessageChannel.WHATSAPP:
            return await self._convert_whatsapp_request(base_message, request)
        elif request.channel in (MessageChannel.PUSH, MessageChannel.WEB_PUSH):
            return await self._convert_push_request(base_message, request)
        else:
            raise IntegrationValidationException(
                f"Unsupported channel: {request.channel}"
            )

    async def _convert_email_request(
        self, message: Dict, request: MessageRequest
    ) -> UpsertMessageDto:
        payload: EmailPayloadRequest = request.payload

        if not payload.text and not payload.html and request.template:
            payload.html = await self._render_template(request)

        if payload.attachments:
            payload.attachments = self._build_attachments(payload.attachments)

        # EmailPayload does not carry attachments in its serialised form —
        # detach, build the DTO, then reattach so downstream has access.
        attachments = payload.attachments
        payload.attachments = None
        email_payload = EmailPayload(**jsonable_encoder(payload, by_alias=False))

        message["payload"] = email_payload
        response = UpsertMessageDto(**message)
        response.payload.attachments = attachments

        return response

    async def _convert_sms_request(
        self, message: Dict, request: MessageRequest
    ) -> UpsertMessageDto:
        payload: SmsPayload = request.payload

        if not payload.text and request.template:
            payload.text = await self._render_template(request)

        message["payload"] = payload
        return UpsertMessageDto(**message)

    async def _convert_whatsapp_request(
        self, message: Dict, request: MessageRequest
    ) -> UpsertMessageDto:
        payload: WhatsappPayload = request.payload

        if not payload.text and request.template:
            payload.text = await self._render_template(request)

        message["payload"] = payload
        return UpsertMessageDto(**message)

    @staticmethod
    async def _convert_push_request(
        message: Dict, request: MessageRequest
    ) -> UpsertMessageDto:
        message["payload"] = request.payload
        return UpsertMessageDto(**message)

    # ------------------------------------------------------------------
    # Supporting methods
    # ------------------------------------------------------------------

    async def _render_template(self, request: MessageRequest) -> Optional[str]:
        if request.template:
            return await self.template_service.render_message(
                channel=request.channel,
                template_name=request.template,
                context=request.template_variables,
            )
        return None

    async def _check_rate_limits(self, message: UpsertMessageDto) -> None:
        tenant = message.extras.get("tenant", "default")
        await self.rate_limiter.check_limit(
            f"{message.channel.value}:{tenant}"
        )

    def _build_attachments(
        self, payloads: List[AttachmentRequest]
    ) -> List[Attachment]:
        """Validate, encode, and return Attachment objects.

        Always returns a list — never None. Callers should check for an
        empty list rather than None.
        """
        attachments: List[Attachment] = []
        for payload in payloads:
            if not payload.file_path.exists():
                raise FileNotFoundError(f"File not found: {payload.file_path}")

            Utils.validate_file_size(payload.file_path, self.MAX_ATTACHMENT_SIZE)

            encoded_content = Base64Utils.file_path_to_base64(payload.file_path)
            guessed_type, _ = mimetypes.guess_type(payload.file_path)
            attachments.append(Attachment(
                content_type=guessed_type or "application/octet-stream",
                filename=payload.filename or payload.file_path.name,
                content=encoded_content,
            ))

        return attachments

    def _track_success(
        self,
        message: UpsertMessageDto,
        result: UpsertMessageDto,
        start_time: datetime,
    ) -> None:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        metrics_manager.track_message(
            channel=message.channel.value,
            provider=result.provider or "unknown",
            status="success",
            duration=duration,
        )

    async def _handle_failure(
        self,
        message: Optional[UpsertMessageDto],
        error: Exception,
    ) -> None:
        """Record failure status and enqueue in DLQ.

        Gracefully exits when message is None — this occurs when conversion
        itself fails before a UpsertMessageDto is ever produced.
        """
        if message is None:
            return

        error_msg = f"{error.__class__.__name__}: {str(error)}"
        message.status = MessageStatus.FAILED
        message.error = error_msg[:500]

        metrics_manager.track_message(
            channel=message.channel.value,
            provider=message.provider or "unknown",
            status="failed",
            duration=0,
        )

        try:
            await self.message_service.update_message_status(
                message.id, message.status, message.error
            )
            # Store only serialisable data — never a live callable.
            # The DLQ processor reconstructs the retry from message ID and channel.
            await self.dlq.add_to_dlq(
                message,
                error_msg,
                extras={"trace_id": message.extras.get("trace_id")},
            )
            logger.info("Message %s added to DLQ", message.id)
        except Exception as dlq_error:
            logger.error(
                "Failed to handle message failure %s: %s",
                message.id, dlq_error,
                exc_info=True,
            )
