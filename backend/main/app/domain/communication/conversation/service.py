"""Conversation (thread) service (PRD §11.1, §26.8).

Owns thread lifecycle: get-or-create the single thread of a channel for a verification
(or a user's general-support thread), the per-user conversation list with unread badges,
and the ``last_message_at`` bump when a message is delivered.

For a WhatsApp thread it also keeps **ownership and membership moving together**: the
portal's conversation list is membership-driven, so an owner who is not a participant never
sees their own thread. Linking a number makes its owner a participant from the moment of
linking; releasing it closes that membership's visibility window, leaving read-only history.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from kink import inject

from main.app.domain.communication.chat_message.models import SenderKind
from main.app.domain.communication.conversation.models import (
    AdminInboxFilter,
    Conversation,
    ConversationChannel,
    ConversationDto,
    ConversationReadOnlyReason,
    ConversationType,
    CreateConversationDto,
)
from main.app.domain.communication.conversation.repo import AdminInboxRow, ConversationRepo
from main.app.domain.communication.conversation_participant.models import (
    ConversationParticipant,
    CreateConversationParticipantDto,
    is_unread,
)
from main.app.domain.communication.conversation_participant.repo import ConversationParticipantRepo
from main.appodus_utils import Page, Utils
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__", "to_dto"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__", "to_dto"], exclude_startswith=["_"])
class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepo,
        participant_repo: ConversationParticipantRepo,
    ):
        self._conversation_repo = conversation_repo
        self._participants = participant_repo

    async def get_or_create_verification_thread(
        self,
        verification_id: str,
        conversation_type: ConversationType,
        created_by: str,
        subject: Optional[str] = None,
    ) -> Conversation:
        existing = await self._conversation_repo.get_for_verification(verification_id, conversation_type)
        if existing:
            return existing
        return await self._conversation_repo.create_return_model(
            CreateConversationDto(
                type=conversation_type,
                verification_id=verification_id,
                subject=subject,
                created_by=created_by,
            )
        )

    async def get_or_create_support_thread(self, user_id: str) -> Conversation:
        existing = await self._conversation_repo.get_general_support(user_id)
        if existing:
            return existing
        return await self._conversation_repo.create_return_model(
            CreateConversationDto(
                type=ConversationType.GENERAL_SUPPORT,
                verification_id=None,
                subject="General support",
                created_by=user_id,
            )
        )

    async def get_or_create_whatsapp_thread(
        self, phone: str, user_id: Optional[str] = None, subject: Optional[str] = None
    ) -> Conversation:
        """The single thread for a WhatsApp number (§26.3.1, §26.8 — one conversation object).

        It is an ordinary general-support thread that happens to have arrived over
        WhatsApp, so once the number is linked to an account the same row simply gains an
        owner — there is no second thread to reconcile. *user_id* is the number's current
        owner, if it has one: a thread first opened **after** linking is created owned, with
        its owner already a member, rather than orphaned from the portal.
        """
        existing = await self._conversation_repo.get_whatsapp_thread(phone)
        if existing:
            return existing
        conversation = await self._conversation_repo.create_return_model(
            CreateConversationDto(
                type=ConversationType.GENERAL_SUPPORT,
                verification_id=None,
                subject=subject or "WhatsApp enquiry",
                created_by=user_id,
                channel=ConversationChannel.WHATSAPP,
                external_ref=phone,
            )
        )
        if user_id:
            await self._open_window(conversation, user_id, Utils.datetime_now())
        return conversation

    async def set_whatsapp_thread_owner(
        self, phone: str, user_id: str, linked_at: datetime
    ) -> Optional[Conversation]:
        """Give the thread for a WhatsApp number its owner, visible from *linked_at*.

        §26.8 wants one conversation object per person, not one per surface, so linking a
        number gives the *existing* thread an owner rather than opening a second one — and
        makes that owner a member, because the portal list only shows memberships. The
        window starts at the link: earlier messages may be a previous holder's. A number
        with no thread yet is a no-op; its first inbound creates the thread owned.
        """
        conversation = await self._conversation_repo.get_whatsapp_thread(phone)
        if conversation is None:
            return None
        conversation.created_by = user_id
        self._conversation_repo._session.add(conversation)
        await self._open_window(conversation, user_id, linked_at)
        return conversation

    async def release_whatsapp_thread(
        self, phone: str, user_id: str, released_at: datetime
    ) -> Optional[Conversation]:
        """Take a WhatsApp thread away from the account that owned it (§26.4.4).

        The thread stays in the console for the agents, but it no longer belongs to anyone,
        so nothing will read case data into it. The former owner's window closes at
        *released_at*: they keep read-only history up to that moment and nothing after it.
        """
        conversation = await self._conversation_repo.get_whatsapp_thread(phone)
        if conversation is None:
            return None
        conversation.created_by = None
        self._conversation_repo._session.add(conversation)
        membership = await self._participants.get_for(conversation.id, user_id)
        if membership is not None and membership.visible_until is None:
            membership.visible_until = released_at
            self._participants._session.add(membership)
        return conversation

    async def get_owned_participant(self, conversation_id: str, user_id: str) -> Conversation:
        """The thread, asserting the user is a participant — raises 404 otherwise (so a
        non-member cannot probe a thread's existence)."""
        participant = await self._participants.get_for(conversation_id, user_id)
        if participant is None:
            raise ResourceNotFoundException(resource="Conversation")
        convo = await self._conversation_repo.get_model(conversation_id)
        if convo is None or convo.deleted:
            raise ResourceNotFoundException(resource="Conversation")
        return convo

    async def get_for_admin(self, conversation_id: str) -> Conversation:
        """Any live thread, without a membership check.

        Admins are a **shared inbox** (§N.3, G4): they are not participants of the threads
        they work, so requiring membership would leave a WhatsApp enquiry readable from the
        console and unanswerable — which is also how D57's take-over would never fire.
        RBAC is enforced at the controller; the caller must already have established that
        this user is an admin.
        """
        convo = await self._conversation_repo.get_model(conversation_id)
        if convo is None or convo.deleted:
            raise ResourceNotFoundException(resource="Conversation")
        return convo

    async def touch(self, conversation: Conversation, at: datetime) -> None:
        """Advance ``last_message_at`` to a delivered message's time (drives unread state).

        Takes the conversation **object**, not its id, on purpose: a thread opened by the
        same request that posts its first message (a WhatsApp enquiry from a new number,
        say) has not been committed yet, and re-fetching it by id returns ``None`` — the
        bump would be silently skipped and the thread would never surface in a list that
        orders by ``last_message_at``. Set on the attached row rather than the update DTO
        path, which json-encodes datetimes.
        """
        conversation.last_message_at = at
        self._conversation_repo._session.add(conversation)

    async def list_for_user(self, user_id: str) -> List[ConversationDto]:
        """The user's threads (Chat conversation list, §N.3), each with its unread count."""
        memberships = await self._participants.list_for_user(user_id)
        by_conv = {m.conversation_id: m for m in memberships}
        conversations = await self._conversation_repo.list_by_ids(list(by_conv.keys()))
        return [
            self.to_dto(convo, membership=by_conv.get(Utils.uuid_to_hex(convo.id)))
            for convo in conversations
        ]

    async def list_admin_inbox(
        self,
        admin_id: str,
        page: int,
        page_size: int,
        *,
        inbox_filter: Optional[AdminInboxFilter] = None,
        query: Optional[str] = None,
    ) -> Page[ConversationDto]:
        """The admin Conversations inbox (§16.5): every thread the console works — cases, web
        support and WhatsApp — server-paged, with unread against this admin's own read state
        (a thread the admin has never opened reads as unread)."""
        rows, total = await self._conversation_repo.list_admin_inbox_page(
            admin_id, page, page_size, inbox_filter=inbox_filter, query=query
        )
        return DbUtils.build_page(
            [self._admin_row_dto(row) for row in rows], total=total, page=page, page_size=page_size
        )

    async def list_for_admin(self, admin_id: str) -> List[ConversationDto]:
        """The same inbox unpaged, for an admin calling the member-facing conversation list."""
        return [self._admin_row_dto(row) for row in await self._conversation_repo.list_admin_inbox(admin_id)]

    async def unread_count_for_admin(self, admin_id: str) -> int:
        """The admin's Chat counter, over exactly the threads the inbox lists."""
        return await self._conversation_repo.count_admin_unread(admin_id)

    @classmethod
    def _admin_row_dto(cls, row: AdminInboxRow) -> ConversationDto:
        return cls.to_dto(
            row.conversation, membership=row.membership,
            owner_name=row.owner_name, owner_email=row.owner_email,
        )

    @staticmethod
    def to_dto(
        convo: Conversation,
        membership: Optional[ConversationParticipant] = None,
        *,
        owner_name: Optional[str] = None,
        owner_email: Optional[str] = None,
    ) -> ConversationDto:
        """The one projection of a thread for a viewer — list rows and thread openers alike.

        *membership* is the viewer's own row: it decides the unread badge and whether the
        thread is read-only for them. Without one (a thread just opened, an admin's first
        look) the thread reads as unread if it has messages, and is writable. The owner is
        passed only by the admin inbox.
        """
        read_only = bool(membership and membership.is_read_only)
        return ConversationDto(
            id=convo.id,
            type=ConversationType(convo.type),
            verification_id=convo.verification_id,
            subject=convo.subject,
            channel=ConversationChannel(convo.channel or ConversationChannel.WEB.value),
            external_ref=convo.external_ref,
            last_message_at=convo.last_message_at,
            closed=convo.closed,
            unread=ConversationService._unread_for(convo, membership),
            read_only=read_only,
            read_only_reason=ConversationReadOnlyReason.NUMBER_UNLINKED if read_only else None,
            owner_name=owner_name,
            owner_email=owner_email,
        )

    @staticmethod
    def _unread_for(convo: Conversation, membership: Optional[ConversationParticipant]) -> int:
        """1 if the viewer has unread messages in the thread, else 0 (the Chat counter counts
        *conversations* with unread, §N.3 — not individual messages)."""
        unread = is_unread(
            convo.last_message_at,
            membership.last_read_at if membership else None,
            membership.visible_from if membership else None,
            membership.visible_until if membership else None,
        )
        return 1 if unread else 0

    async def _open_window(self, conversation: Conversation, user_id: str, at: datetime) -> None:
        """Make *user_id* a member of *conversation*, able to see it from *at* onwards.

        An existing membership is reopened with a fresh start rather than extended: the
        number may have belonged to another account in between, and those messages are not
        this member's to read.
        """
        membership = await self._participants.get_for(conversation.id, user_id)
        if membership is None:
            await self._participants.create_return_model(
                CreateConversationParticipantDto(
                    conversation_id=Utils.uuid_to_hex(conversation.id),
                    user_id=str(user_id),
                    role=SenderKind.CUSTOMER.value,
                    visible_from=at,
                )
            )
            return
        membership.visible_from = at
        membership.visible_until = None
        self._participants._session.add(membership)
