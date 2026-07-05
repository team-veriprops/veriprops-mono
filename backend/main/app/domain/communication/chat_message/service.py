"""Chat message service (PRD §11.1, §11.2, §4.7).

The orchestrator of the communication layer: send-time fraud scan + hold state machine
(§4.7), admin hold-review approve/reject, the thread message feed with the customer-safe
sender projection (§11.3), and best-effort SSE fan-out to a thread's other participants.

Delivery correctness never depends on the push: the message row is the source of truth and
the poll fallback reconciles (§4.9). Every held/approve/reject decision is audit-logged so
the false-positive rate can be instrumented from day one (§4.7).
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.machine import chat_message_state_machine
from main.app.core.state.status import ChatMessageState
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.communication.chat_message.models import (
    BODY_MAX_LENGTH,
    ChatMessage,
    ChatMessageDto,
    ChatSenderDto,
    ClarificationStatus,
    CreateChatMessageDto,
    HeldMessageDto,
    MessageKind,
    SenderKind,
)
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)
from main.app.domain.communication.fraud_scan import scan_message
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Page, Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)

# Sender-facing notice while a message is held for review (§11.2) — worded so it never
# reads as suspicion of the sender.
HELD_NOTICE = "Just a moment while we check this through."


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ChatMessageService:
    def __init__(
        self,
        chat_message_repo: ChatMessageRepo,
        conversation_service: ConversationService,
        participant_service: ConversationParticipantService,
        user_repo: UserRepo,
        audit: AuditLogService,
    ):
        self._repo = chat_message_repo
        self._conversations = conversation_service
        self._participants = participant_service
        self._users = user_repo
        self._audit = audit

    # ── Send (§11.2 fast lane / hold) ─────────────────────────────────

    async def send(
        self,
        conversation: Conversation,
        sender_user_id: Optional[str],
        sender_kind: SenderKind,
        body: str,
        *,
        task_id: Optional[str] = None,
        kind: MessageKind = MessageKind.CHAT,
    ) -> ChatMessage:
        """Send a message into a thread. Clean messages deliver immediately (fast lane);
        flagged messages are held for admin review (§4.7)."""
        body = (body or "").strip()
        if not body:
            raise ValidationException(message="Message body is required")
        if len(body) > BODY_MAX_LENGTH:
            raise ValidationException(
                message=f"Message exceeds the {BODY_MAX_LENGTH}-character limit"
            )

        categories = scan_message(body)
        now = Utils.datetime_now()
        held = bool(categories)

        clarification_status = (
            ClarificationStatus.OPEN if kind == MessageKind.CLARIFICATION_REQUEST else None
        )

        message = await self._repo.create_return_model(
            CreateChatMessageDto(
                conversation_id=conversation.id,
                sender_user_id=sender_user_id,
                sender_kind=sender_kind,
                body=body,
                task_id=task_id,
                state=ChatMessageState.HELD if held else ChatMessageState.DELIVERED,
                message_kind=kind,
                clarification_status=clarification_status,
                flagged_categories=[c.value for c in categories] or None,
                held_at=now if held else None,
                delivered_at=None if held else now,
            )
        )

        if sender_user_id:
            await self._participants.ensure_participant(conversation.id, sender_user_id)

        if held:
            self._audit.schedule(
                action=AuditActionType.MESSAGE_HELD,
                resource_type="ChatMessage",
                resource_id=message.id,
                actor_id=sender_user_id,
                details={"categories": [c.value for c in categories]},
            )
        else:
            await self._deliver_effects(conversation, message, sender_user_id)
            self._audit.schedule(
                action=AuditActionType.MESSAGE_SENT,
                resource_type="ChatMessage",
                resource_id=message.id,
                actor_id=sender_user_id,
            )
        return message

    # ── Admin hold review (§11.2) ─────────────────────────────────────

    async def approve(self, message_id: str, admin_id: str) -> ChatMessage:
        """Release a held message (HELD → DELIVERED) and fan it out."""
        message = await self._get_held(message_id)
        chat_message_state_machine.assert_can_transition(
            message.state, ChatMessageState.DELIVERED.value, resource="ChatMessage"
        )
        now = Utils.datetime_now()
        message.state = ChatMessageState.DELIVERED.value
        message.delivered_at = now
        message.reviewed_by = admin_id
        message.reviewed_at = now
        self._repo._session.add(message)

        conversation = await self._conversations._repo.get_model(message.conversation_id)
        if conversation is not None:
            await self._deliver_effects(conversation, message, message.sender_user_id)
        self._audit.schedule(
            action=AuditActionType.MESSAGE_APPROVED,
            resource_type="ChatMessage",
            resource_id=message.id,
            actor_id=admin_id,
        )
        return message

    async def reject(self, message_id: str, admin_id: str) -> ChatMessage:
        """Block a held message (HELD → BLOCKED). It never reaches the recipient (§11.2)."""
        message = await self._get_held(message_id)
        chat_message_state_machine.assert_can_transition(
            message.state, ChatMessageState.BLOCKED.value, resource="ChatMessage"
        )
        now = Utils.datetime_now()
        message.state = ChatMessageState.BLOCKED.value
        message.reviewed_by = admin_id
        message.reviewed_at = now
        self._repo._session.add(message)
        self._audit.schedule(
            action=AuditActionType.MESSAGE_REJECTED,
            resource_type="ChatMessage",
            resource_id=message.id,
            actor_id=admin_id,
        )
        return message

    async def _get_held(self, message_id: str) -> ChatMessage:
        message = await self._repo.get_model(message_id)
        if message is None or message.deleted:
            raise ResourceNotFoundException(resource="ChatMessage")
        if message.state != ChatMessageState.HELD.value:
            raise ForbiddenException(message="Only held messages can be reviewed")
        return message

    # ── Feeds & projections ───────────────────────────────────────────

    async def list_messages(
        self, conversation_id: str, viewer_id: Optional[str], page: int, page_size: int
    ) -> Page[ChatMessageDto]:
        raw = await self._repo.list_delivered_page(conversation_id, viewer_id, page, page_size)
        dtos = [await self._to_dto(m, viewer_id) for m in raw.items]
        return Page[ChatMessageDto](items=dtos, meta=raw.meta)

    async def held_queue(self, page: int, page_size: int) -> Page[HeldMessageDto]:
        raw = await self._repo.list_held_page(page, page_size)
        items = [await self._to_held_dto(m) for m in raw.items]
        return Page[HeldMessageDto](items=items, meta=raw.meta)

    async def held_count(self) -> int:
        return await self._repo.held_count()

    # ── Internal helpers ──────────────────────────────────────────────

    async def _deliver_effects(
        self, conversation: Conversation, message: ChatMessage, sender_user_id: Optional[str]
    ) -> None:
        """Bump the thread timestamp and publish MESSAGE_SENT on the §4.8 bus. The
        chat-counter subscriber pushes the Chat counter to the other participants; the rule
        table keeps a routine message out of Notifications (§12.3)."""
        await self._conversations.touch(conversation.id, message.delivered_at or Utils.datetime_now())
        participants = await self._participants._repo.list_for_conversation(conversation.id)
        recipients = tuple(p.user_id for p in participants if p.user_id != sender_user_id)
        await publish_domain_event(DomainEvent(
            type=EventType.MESSAGE_SENT,
            verification_id=conversation.verification_id,
            recipient_user_ids=recipients,
            data={"conversation_id": conversation.id},
        ))

    async def _to_dto(self, message: ChatMessage, viewer_id: Optional[str]) -> ChatMessageDto:
        held_notice = None
        if (
            message.state in (ChatMessageState.HELD.value, ChatMessageState.PENDING_SCAN.value)
            and viewer_id is not None
            and message.sender_user_id == viewer_id
        ):
            held_notice = HELD_NOTICE
        return ChatMessageDto(
            id=message.id,
            conversation_id=message.conversation_id,
            body=message.body,
            task_id=message.task_id,
            state=ChatMessageState(message.state),
            message_kind=MessageKind(message.message_kind),
            clarification_status=(
                ClarificationStatus(message.clarification_status)
                if message.clarification_status
                else None
            ),
            sender=await self._sender_dto(message),
            held_notice=held_notice,
            date_created=message.date_created,
            delivered_at=message.delivered_at,
        )

    async def _sender_dto(self, message: ChatMessage) -> ChatSenderDto:
        """Customer-safe sender identity (§11.3): first name + avatar only — never last
        name, email, or phone, regardless of the sender's role."""
        kind = SenderKind(message.sender_kind)
        if kind == SenderKind.SYSTEM or not message.sender_user_id:
            return ChatSenderDto(kind=SenderKind.SYSTEM)
        user = await self._users.get_model(message.sender_user_id)
        return ChatSenderDto(
            user_id=message.sender_user_id,
            kind=kind,
            first_name=getattr(user, "first_name", None) if user else None,
            avatar_url=getattr(user, "avatar_url", None) if user else None,
        )

    async def _to_held_dto(self, message: ChatMessage) -> HeldMessageDto:
        conversation = await self._conversations._repo.get_model(message.conversation_id)
        return HeldMessageDto(
            id=message.id,
            conversation_id=message.conversation_id,
            conversation_type=conversation.type if conversation else None,
            verification_id=conversation.verification_id if conversation else None,
            sender_user_id=message.sender_user_id,
            sender_kind=SenderKind(message.sender_kind),
            body=message.body,
            flagged_categories=list(message.flagged_categories or []),
            held_at=message.held_at,
            date_created=message.date_created,
        )
