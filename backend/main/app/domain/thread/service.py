"""Thread service — per-verification messaging with Redis fan-out (S37)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional

from kink import di, inject

from main.app.domain.thread.models import (
    CreateThreadDto,
    CreateThreadMessageDto,
    MessageThread,
    MessageType,
    PostMessageDto,
    SenderRole,
    ThreadDto,
    ThreadMessageDto,
    ThreadType,
    UpdateThreadMessageDto,
)
from main.app.domain.thread.repo import ThreadMessageRepo, ThreadRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ForbiddenException, ResourceNotFoundException

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]

_AGENT_IDENTITY_PROTECTED_FIELDS = ("last_name", "email", "phone", "contact")


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ThreadService:
    def __init__(
        self,
        thread_repo: ThreadRepo,
        message_repo: ThreadMessageRepo,
    ):
        self._threads = thread_repo
        self._messages = message_repo

    async def get_or_create_thread(
        self,
        verification_id: str,
        thread_type: ThreadType,
        task_id: Optional[str] = None,
    ) -> ThreadDto:
        existing: Optional[MessageThread] = None
        if task_id:
            existing = await self._threads.get_by_task(task_id, thread_type)
        else:
            existing = await self._threads.get_by_verification_and_type(verification_id, thread_type)

        if existing:
            return self._to_thread_dto(existing)

        created = await self._threads.create_return_model(
            CreateThreadDto(
                thread_type=thread_type,
                verification_id=verification_id,
                task_id=task_id,
            )
        )
        return self._to_thread_dto(created)

    async def post_message(
        self,
        thread_id: str,
        sender_id: str,
        sender_role: SenderRole,
        dto: PostMessageDto,
    ) -> ThreadMessageDto:
        thread = await self._threads.get_model(thread_id)
        if thread is None:
            raise ResourceNotFoundException(resource="Thread")

        body = dto.body
        is_held = False

        # Integrate fraud detection if available
        try:
            from main.app.domain.thread.fraud.service import FraudDetectionService
            fraud_svc: FraudDetectionService = di[FraudDetectionService]
            matched = fraud_svc.scan(body)
            if matched:
                is_held = True
                await fraud_svc.record_flag(
                    message_body=body,
                    matched_patterns=matched,
                )
        except Exception:
            pass

        msg = await self._messages.create_return_model(
            CreateThreadMessageDto(
                thread_id=thread_id,
                sender_id=sender_id,
                sender_role=sender_role,
                message_type=MessageType.TEXT,
                body=body,
                attachment_key=dto.attachment_key,
                is_held=is_held,
            )
        )
        if not is_held:
            await self._publish(thread.verification_id, thread_id, msg.id, body, sender_role.value)
            await self._emit_new_message_safe(thread, sender_role, msg)

        return self._to_msg_dto(msg)

    async def post_system_message(self, thread_id: str, body: str) -> ThreadMessageDto:
        thread = await self._threads.get_model(thread_id)
        if thread is None:
            return  # thread may not exist yet for this verification state

        msg = await self._messages.create_return_model(
            CreateThreadMessageDto(
                thread_id=thread_id,
                sender_id=None,
                sender_role=SenderRole.SYSTEM,
                message_type=MessageType.SYSTEM,
                body=body,
                is_held=False,
            )
        )
        await self._publish(thread.verification_id, thread_id, msg.id, body, "SYSTEM")
        return self._to_msg_dto(msg)

    async def post_system_message_for_verification(
        self, verification_id: str, thread_type: ThreadType, body: str, task_id: Optional[str] = None
    ) -> None:
        """Auto-create or find the thread and post a system message."""
        thread = await self.get_or_create_thread(verification_id, thread_type, task_id=task_id)
        await self.post_system_message(thread.id, body)

    async def broadcast_to_verification(self, verification_id: str, body: str) -> None:
        """Post a system message to all threads on a verification."""
        threads = await self._threads.list_for_verification(verification_id)
        for thread in threads:
            await self.post_system_message(str(thread.id), body)

    async def list_messages(self, thread_id: str, limit: int = 50) -> List[ThreadMessageDto]:
        msgs = await self._messages.list_for_thread(thread_id, limit=limit)
        return [self._to_msg_dto(m) for m in msgs]

    async def release_held_message(self, message_id: str) -> ThreadMessageDto:
        msg = await self._messages.get_model(message_id)
        if msg is None:
            raise ResourceNotFoundException(resource="ThreadMessage")
        await self._messages.update(message_id, UpdateThreadMessageDto(is_held=False))
        msg = await self._messages.get_model(message_id)
        thread = await self._threads.get_model(msg.thread_id)
        await self._publish(thread.verification_id, msg.thread_id, message_id, msg.body, msg.sender_role)
        return self._to_msg_dto(msg)

    async def discard_held_message(self, message_id: str) -> None:
        msg = await self._messages.get_model(message_id)
        if msg is None:
            raise ResourceNotFoundException(resource="ThreadMessage")
        await self._messages.update(message_id, UpdateThreadMessageDto(is_held=False))
        # Soft-delete via repo
        session = self._messages._session
        from sqlalchemy import update as sa_update
        from main.app.domain.thread.models import ThreadMessage
        await session.execute(
            sa_update(ThreadMessage)
            .where(ThreadMessage.id == msg.id)
            .values(deleted=True)
        )

    # ── Helpers ───────────────────────────────────────────────────

    async def _emit_new_message_safe(self, thread, sender_role: SenderRole, msg) -> None:
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            notif_svc: NotificationService = di[NotificationService]
            recipient_id = None
            if thread.thread_type == ThreadType.CUSTOMER_ADMIN.value and sender_role == SenderRole.ADMIN:
                from main.app.domain.verification.repo import VerificationRepo
                ver = await di[VerificationRepo].get(str(thread.verification_id))
                if ver:
                    recipient_id = str(ver.customer_id)
            elif thread.thread_type == ThreadType.ADMIN_AGENT.value and sender_role == SenderRole.ADMIN:
                if thread.task_id:
                    from main.app.domain.verification.task.repo import TaskRepo
                    task = await di[TaskRepo].get_task(str(thread.task_id))
                    if task and task.agent_id:
                        recipient_id = str(task.agent_id)
            if recipient_id:
                await notif_svc.emit(
                    NotificationEvent.NEW_MESSAGE,
                    recipient_id=recipient_id,
                    context={},
                    entity_type="Thread",
                    entity_id=str(thread.id),
                )
        except Exception as exc:
            logger.warning(f"NEW_MESSAGE notification emit failed: {exc}")

    async def _publish(
        self,
        verification_id: str,
        thread_id: str,
        message_id: str,
        body: str,
        sender_role: str,
    ) -> None:
        try:
            from kink import di
            from redis.asyncio import Redis
            redis_client: Redis = di[Redis]
            payload = json.dumps({
                "event": "new_message",
                "thread_id": thread_id,
                "message_id": message_id,
                "body": body if sender_role != "AGENT" else body,
                "sender_role": sender_role,
            })
            await redis_client.publish(f"thread:{thread_id}", payload)
        except Exception as exc:
            logger.warning("Redis publish failed for thread {}: {}", thread_id, exc)

    @staticmethod
    def _to_thread_dto(row: MessageThread) -> ThreadDto:
        return ThreadDto(
            id=str(row.id),
            thread_type=ThreadType(row.thread_type),
            verification_id=row.verification_id,
            task_id=row.task_id,
            date_created=row.date_created,
        )

    @staticmethod
    def _to_msg_dto(row) -> ThreadMessageDto:
        return ThreadMessageDto(
            id=str(row.id),
            thread_id=row.thread_id,
            sender_id=row.sender_id,
            sender_role=SenderRole(row.sender_role),
            message_type=MessageType(row.message_type),
            body=row.body,
            attachment_key=row.attachment_key,
            is_held=row.is_held,
            date_created=row.date_created,
        )
