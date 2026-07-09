"""Communication façade (PRD §11) — orchestration only, no entity of its own.

Resolves the right thread for each actor with the right authorization gate, then delegates
to the per-entity services (conversation / participant / chat_message). Ownership rules:

- **Customer ↔ Admin**: the customer must own the verification (``VerificationService.get_owned``).
- **Admin ↔ Agent**: the agent must be assigned to a task on the verification; a task's
  messages go read-only to the agent once that task is ``APPROVED`` (§11.1).
- **General support**: the user's own single thread (§N.2).

Admin RBAC is enforced at the controller (``require_permission``); this service trusts the
admin id it is handed.
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.core.state.status import TaskState
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.repo import UserRepo
from main.app.domain.communication.chat_message.models import (
    ChatMessage,
    ChatMessageDto,
    HeldMessageDto,
    MessageKind,
    SenderKind,
)
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import Conversation, ConversationDto, ConversationType
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ForbiddenException, ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommunicationService:
    def __init__(
        self,
        conversation_service: ConversationService,
        participant_service: ConversationParticipantService,
        chat_message_service: ChatMessageService,
        verification_service: VerificationService,
        task_repo: VerificationTaskRepo,
        user_repo: UserRepo,
    ):
        self._conversations = conversation_service
        self._participants = participant_service
        self._chat = chat_message_service
        self._verifications = verification_service
        self._tasks = task_repo
        self._users = user_repo

    async def _is_admin(self, user_id: str) -> bool:
        user = await self._users.get_model(user_id)
        return bool(user and user.user_type == UserType.ADMIN.value)

    # ── Conversation list & read state (§N.3) ─────────────────────────

    async def list_conversations(self, user_id: str) -> List[ConversationDto]:
        # Admins are a shared inbox — they see every verification thread (§N.3, G4).
        if await self._is_admin(user_id):
            return await self._conversations.list_for_admin(user_id)
        return await self._conversations.list_for_user(user_id)

    async def unread_count(self, user_id: str) -> int:
        if await self._is_admin(user_id):
            return await self._conversations.unread_count_for_admin(user_id)
        return await self._participants.unread_conversation_count(user_id)

    async def mark_read(self, conversation_id: str, user_id: str) -> None:
        # Admins may read any verification thread; others must be a participant.
        if not await self._is_admin(user_id):
            await self._conversations.get_owned_participant(conversation_id, user_id)
        await self._participants.mark_read(conversation_id, user_id)

    async def list_messages(
        self, conversation_id: str, user_id: str, page: int, page_size: int
    ) -> Page[ChatMessageDto]:
        if not await self._is_admin(user_id):
            await self._conversations.get_owned_participant(conversation_id, user_id)
        return await self._chat.list_messages(conversation_id, user_id, page, page_size)

    async def post_message(
        self,
        conversation_id: str,
        user_id: str,
        body: str,
        *,
        task_id: Optional[str] = None,
        kind: MessageKind = MessageKind.CHAT,
    ) -> ChatMessage:
        """Send into a thread the user is a member of. ``sender_kind`` is derived
        server-side from the caller's role and the thread type — never trusted from the
        client — so a member cannot post as ADMIN/SYSTEM. Membership is the base
        authorization, and an agent posting about an approved task is refused (§11.1)."""
        convo = await self._conversations.get_owned_participant(conversation_id, user_id)
        sender_kind = await self._resolve_sender_kind(user_id, convo)
        if sender_kind == SenderKind.AGENT and task_id:
            await self._assert_task_writable(task_id, user_id)
        return await self._chat.send(convo, user_id, sender_kind, body, task_id=task_id, kind=kind)

    async def _resolve_sender_kind(self, user_id: str, convo: Conversation) -> SenderKind:
        """Trusted sender identity for the generic post path: admins post as ADMIN, the
        non-admin party in an admin↔agent thread posts as AGENT, everyone else as
        CUSTOMER. SYSTEM is never assignable to a human-originated message."""
        if await self._is_admin(user_id):
            return SenderKind.ADMIN
        if convo.type == ConversationType.ADMIN_AGENT.value:
            return SenderKind.AGENT
        return SenderKind.CUSTOMER

    # ── Customer ↔ Admin (§11.1) ──────────────────────────────────────

    async def customer_thread(self, verification_id: str, customer_id: str) -> Conversation:
        await self._verifications.get_owned(verification_id, customer_id)  # ownership gate
        convo = await self._conversations.get_or_create_verification_thread(
            verification_id, ConversationType.CUSTOMER_ADMIN, created_by=customer_id
        )
        await self._participants.ensure_participant(convo.id, customer_id, role="CUSTOMER")
        return convo

    async def customer_send(
        self, verification_id: str, customer_id: str, body: str, kind: MessageKind = MessageKind.CHAT
    ) -> ChatMessage:
        convo = await self.customer_thread(verification_id, customer_id)
        return await self._chat.send(convo, customer_id, SenderKind.CUSTOMER, body, kind=kind)

    # ── General support (§N.2) ────────────────────────────────────────

    async def support_thread(self, user_id: str) -> Conversation:
        convo = await self._conversations.get_or_create_support_thread(user_id)
        await self._participants.ensure_participant(convo.id, user_id, role="CUSTOMER")
        return convo

    async def support_send(self, user_id: str, body: str) -> ChatMessage:
        convo = await self.support_thread(user_id)
        return await self._chat.send(convo, user_id, SenderKind.CUSTOMER, body)

    # ── Admin ↔ Agent (§11.1) ─────────────────────────────────────────

    async def agent_thread(self, verification_id: str, agent_id: str) -> Conversation:
        await self._assert_agent_on_verification(verification_id, agent_id)
        convo = await self._conversations.get_or_create_verification_thread(
            verification_id, ConversationType.ADMIN_AGENT, created_by=agent_id
        )
        await self._participants.ensure_participant(convo.id, agent_id, role="AGENT")
        return convo

    async def agent_send(
        self, verification_id: str, agent_id: str, body: str, task_id: Optional[str] = None
    ) -> ChatMessage:
        await self._assert_agent_on_verification(verification_id, agent_id)
        if task_id:
            await self._assert_task_writable(task_id, agent_id)
        convo = await self.agent_thread(verification_id, agent_id)
        return await self._chat.send(convo, agent_id, SenderKind.AGENT, body, task_id=task_id)

    async def admin_thread(
        self, verification_id: str, conversation_type: ConversationType, admin_id: str
    ) -> Conversation:
        convo = await self._conversations.get_or_create_verification_thread(
            verification_id, conversation_type, created_by=admin_id
        )
        await self._participants.ensure_participant(convo.id, admin_id, role="ADMIN")
        return convo

    async def admin_send(
        self,
        verification_id: str,
        conversation_type: ConversationType,
        admin_id: str,
        body: str,
        task_id: Optional[str] = None,
    ) -> ChatMessage:
        convo = await self.admin_thread(verification_id, conversation_type, admin_id)
        return await self._chat.send(convo, admin_id, SenderKind.ADMIN, body, task_id=task_id)

    # ── Admin hold review (§11.2) ─────────────────────────────────────

    async def held_queue(self, page: int, page_size: int) -> Page[HeldMessageDto]:
        return await self._chat.held_queue(page, page_size)

    async def approve_message(self, message_id: str, admin_id: str) -> ChatMessage:
        return await self._chat.approve(message_id, admin_id)

    async def reject_message(self, message_id: str, admin_id: str) -> ChatMessage:
        return await self._chat.reject(message_id, admin_id)

    # ── System auto-posts (§11.1) ─────────────────────────────────────

    async def auto_post_customer(self, verification_id: str, customer_id: str, body: str) -> None:
        """Auto-post a system message into the Customer↔Admin thread (e.g. a status change).

        Best-effort orchestration hook — the thread is created on demand; a system message
        skips the fraud scan (it is platform-authored) and delivers immediately."""
        convo = await self._conversations.get_or_create_verification_thread(
            verification_id, ConversationType.CUSTOMER_ADMIN, created_by=customer_id
        )
        await self._participants.ensure_participant(convo.id, customer_id, role="CUSTOMER")
        await self._chat.send(convo, None, SenderKind.SYSTEM, body, kind=MessageKind.SYSTEM_AUTO)

    async def auto_post_agent(
        self, verification_id: str, agent_id: Optional[str], body: str, task_id: Optional[str] = None
    ) -> None:
        """Auto-post a system message into the Admin↔Agent thread (e.g. a rejection reason
        tagged to the task, §11.1)."""
        creator = agent_id or verification_id
        convo = await self._conversations.get_or_create_verification_thread(
            verification_id, ConversationType.ADMIN_AGENT, created_by=creator
        )
        if agent_id:
            await self._participants.ensure_participant(convo.id, agent_id, role="AGENT")
        await self._chat.send(
            convo, None, SenderKind.SYSTEM, body, task_id=task_id, kind=MessageKind.SYSTEM_AUTO
        )

    # ── Internal authz helpers ────────────────────────────────────────

    async def _assert_agent_on_verification(self, verification_id: str, agent_id: str) -> None:
        tasks = await self._tasks.list_for_verification(verification_id)
        if not any(t.assigned_agent_id == agent_id for t in tasks):
            raise ForbiddenException(message="You are not assigned to this verification")

    async def _assert_task_writable(self, task_id: str, agent_id: str) -> None:
        task = await self._tasks.get_model(task_id)
        if task is None or task.deleted:
            raise ResourceNotFoundException(resource="Task")
        if task.assigned_agent_id != agent_id:
            raise ForbiddenException(message="You are not assigned to this task")
        # A task's messages go read-only to the agent once that task is APPROVED (§11.1).
        if task.state == TaskState.APPROVED.value:
            raise ForbiddenException(message="This task is approved; its thread is read-only")
