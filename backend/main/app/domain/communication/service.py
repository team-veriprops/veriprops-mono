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

from logging import Logger
from typing import TYPE_CHECKING, List, Optional

from kink import di, inject

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
from main.app.domain.communication.conversation.models import (
    AdminInboxFilter,
    Conversation,
    ConversationChannel,
    ConversationDto,
    ConversationType,
)
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Page, Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidResourceStateException,
    ResourceNotFoundException,
)

if TYPE_CHECKING:
    from main.app.domain.communication.assistant.web import AssistantOutcome

logger: Logger = di["logger"]


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
        # Admins are a shared inbox — they see every thread the console works (§16.5, G4).
        if await self._is_admin(user_id):
            return await self._conversations.list_for_admin(user_id)
        return await self._with_assistant_pending(await self._conversations.list_for_user(user_id))

    async def conversation_dto(self, convo: Conversation) -> ConversationDto:
        """A thread opener's response: the list projection, plus whether the assistant still
        owes an answer — a page reloaded mid-turn shows the typing state and asks again."""
        [dto] = await self._with_assistant_pending([ConversationService.to_dto(convo)])
        return dto

    async def _with_assistant_pending(self, dtos: List[ConversationDto]) -> List[ConversationDto]:
        from main.app.domain.communication.assistant.web import WebAssistantService

        pending = await di[WebAssistantService].pending_conversation_ids([d.id for d in dtos])
        for dto in dtos:
            dto.assistant_pending = Utils.uuid_to_hex(dto.id) in pending
        return dtos

    # ── The assistant on web threads (§16.7, D93) ─────────────────────

    async def answer_with_assistant(self, message: ChatMessage) -> "AssistantOutcome":
        """Let the assistant answer a customer's just-sent message, in phase one.

        Runs after the send has committed and never fails it: the customer's message is in the
        thread whatever the assistant does, and an assistant fault already becomes a warm
        handover inside the engine.
        """
        from main.app.domain.communication.assistant.web import (
            AssistantOutcome,
            WebAssistantService,
        )

        try:
            convo = await self._conversations.get_for_admin(message.conversation_id)
            return await di[WebAssistantService].after_customer_message(convo, message)
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.error(f"Assistant did not run for message {message.id}: {exc}")
            return AssistantOutcome()

    async def run_assistant_turn(self, conversation_id: str, user_id: str) -> "AssistantOutcome":
        """Phase two, asked for by a member of the thread (D93). Membership is the gate; the
        party the assistant talks to is still derived from the thread, never from the caller."""
        from main.app.domain.communication.assistant.web import WebAssistantService

        await self._conversations.get_owned_participant(conversation_id, user_id)
        return await di[WebAssistantService].run_pending_turn(conversation_id)

    async def unread_count(self, user_id: str) -> int:
        if await self._is_admin(user_id):
            return await self._conversations.unread_count_for_admin(user_id)
        return await self._participants.unread_conversation_count(user_id)

    async def admin_inbox(
        self,
        admin_id: str,
        page: int,
        page_size: int,
        *,
        inbox_filter: Optional[AdminInboxFilter] = None,
        query: Optional[str] = None,
    ) -> Page[ConversationDto]:
        """The console's Conversations inbox (§16.5). RBAC is enforced at the controller."""
        return await self._conversations.list_admin_inbox(
            admin_id, page, page_size, inbox_filter=inbox_filter, query=query
        )

    async def mark_read(self, conversation_id: str, user_id: str) -> None:
        """Stamp the viewer's read state. Admins may read any thread; others must be a
        participant — and a customer reading their WhatsApp thread in the portal also stops
        queued replies they have now seen from going to their phone later (D92)."""
        if await self._is_admin(user_id):
            await self._participants.mark_read(conversation_id, user_id)
            return
        convo = await self._conversations.get_owned_participant(conversation_id, user_id)
        await self._participants.mark_read(conversation_id, user_id)
        if convo.channel == ConversationChannel.WHATSAPP.value:
            await self._cancel_phone_delivery_read_in_portal(conversation_id, user_id)

    async def _cancel_phone_delivery_read_in_portal(self, conversation_id: str, user_id: str) -> None:
        """Only an open window counts: a former owner reading their history has not seen the
        replies now queued for whoever holds the number."""
        membership = await self._participants.get_membership(conversation_id, user_id)
        if membership is None or membership.is_read_only:
            return
        await self._chat.cancel_pending_channel_delivery(
            conversation_id, read_at=Utils.datetime_now(), visible_from=membership.visible_from
        )

    async def list_messages(
        self, conversation_id: str, user_id: str, page: int, page_size: int
    ) -> Page[ChatMessageDto]:
        """The thread feed for a viewer. Admins read everything (shared inbox); a member
        reads only inside their visibility window (§26.8) — which is the whole thread for
        every web membership."""
        membership = None
        is_admin = await self._is_admin(user_id)
        if not is_admin:
            await self._conversations.get_owned_participant(conversation_id, user_id)
            membership = await self._participants.get_membership(conversation_id, user_id)
        return await self._chat.list_messages(
            conversation_id, user_id, page, page_size,
            visible_from=membership.visible_from if membership else None,
            visible_until=membership.visible_until if membership else None,
            viewer_is_admin=is_admin,
        )

    async def post_message(
        self,
        conversation_id: str,
        user_id: str,
        body: str,
        *,
        task_id: Optional[str] = None,
    ) -> ChatMessage:
        """Send into a thread the user may write to. ``sender_kind`` is derived
        server-side from the caller's role and the thread type — never trusted from the
        client — so a member cannot post as ADMIN/SYSTEM. The message kind is always
        ``CHAT`` for the same reason: ``SYSTEM_AUTO`` exempts platform copy from the fraud
        scan, so it is reachable only from platform callers that use ``ChatMessageService``
        directly. Membership is the base authorization, and an agent posting about an
        approved task is refused (§11.1).

        **Admins are the exception, as they already are for reading.** They work a shared
        inbox rather than joining threads (§N.3, G4) — `list_conversations`, `mark_read`
        and `list_messages` all say so — and a WhatsApp enquiry has no admin participant
        at all. Requiring membership here made every such thread readable from the console
        and unanswerable, which also meant D57's bot take-over could never fire.
        """
        if await self._is_admin(user_id):
            convo = await self._conversations.get_for_admin(conversation_id)
        else:
            convo = await self._conversations.get_owned_participant(conversation_id, user_id)
            await self._assert_membership_writable(conversation_id, user_id)
        sender_kind = await self._resolve_sender_kind(user_id, convo)
        if sender_kind == SenderKind.AGENT and task_id:
            await self._assert_task_writable(task_id, user_id)
        message = await self._chat.send(
            convo, user_id, sender_kind, body, task_id=task_id, kind=MessageKind.CHAT
        )
        await self._silence_the_assistant_if_a_human_joined(convo, sender_kind)
        return message

    async def _silence_the_assistant_if_a_human_joined(
        self, convo: Conversation, sender_kind: SenderKind
    ) -> None:
        """D57 — a person replying on a thread the assistant answers takes it off the assistant.

        Any such thread: a WhatsApp enquiry, a web support thread, a case's customer thread.
        The trigger is a *human* speaking, not an escalation: a customer whose question
        nobody has picked up yet should still get answers to their next question, rather
        than silence. Sticky until someone hands back from the console.

        Best-effort. The reply has already been sent and delivered; failing the request
        now would tell an agent their message did not go through when it did.
        """
        if sender_kind not in (SenderKind.ADMIN, SenderKind.AGENT):
            return
        from main.app.domain.communication.assistant.session.service import (
            AssistantSessionService,
        )
        from main.app.domain.communication.assistant.surface import assistant_surface_for

        if assistant_surface_for(convo) is None:
            return
        try:
            await di[AssistantSessionService].take_over(convo)
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.error(f"Could not hand conversation {convo.id} to the agent: {exc}")

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

    async def customer_send(self, verification_id: str, customer_id: str, body: str) -> ChatMessage:
        convo = await self.customer_thread(verification_id, customer_id)
        return await self._chat.send(
            convo, customer_id, SenderKind.CUSTOMER, body, kind=MessageKind.CHAT
        )

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
        message = await self._chat.send(convo, admin_id, SenderKind.ADMIN, body, task_id=task_id)
        await self._silence_the_assistant_if_a_human_joined(convo, SenderKind.ADMIN)
        return message

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

    async def _assert_membership_writable(self, conversation_id: str, user_id: str) -> None:
        """A closed visibility window (a released WhatsApp number, §26.4.4) leaves read-only
        history. Refused as an invalid state rather than a 403: the web client hard-navigates
        to /forbidden on any 403, which would replace the thread the customer is reading."""
        membership = await self._participants.get_membership(conversation_id, user_id)
        if membership is not None and membership.is_read_only:
            raise InvalidResourceStateException(
                resource="Conversation",
                message="This conversation is read-only because the WhatsApp number was unlinked.",
            )

    async def _assert_task_writable(self, task_id: str, agent_id: str) -> None:
        task = await self._tasks.get_model(task_id)
        if task is None or task.deleted:
            raise ResourceNotFoundException(resource="Task")
        if task.assigned_agent_id != agent_id:
            raise ForbiddenException(message="You are not assigned to this task")
        # A task's messages go read-only to the agent once that task is APPROVED (§11.1).
        if task.state == TaskState.APPROVED.value:
            raise ForbiddenException(message="This task is approved; its thread is read-only")
