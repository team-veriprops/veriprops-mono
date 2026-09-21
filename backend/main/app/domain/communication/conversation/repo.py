"""Conversation data access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import String, and_, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.communication.conversation.models import (
    AdminInboxFilter,
    Conversation,
    ConversationChannel,
    ConversationType,
    CreateConversationDto,
    QueryConversationDto,
    SearchConversationDto,
    UpdateConversationDto,
)
from main.app.domain.communication.conversation_participant.models import ConversationParticipant
from main.app.domain.communication.conversation_participant.repo import (
    joins_conversation,
    unread_condition,
)
from main.app.domain.user.models import User
from main.appodus_utils.db.repo import GenericRepo


@inject
class ConversationRepo(
    GenericRepo[
        Conversation,
        CreateConversationDto,
        UpdateConversationDto,
        QueryConversationDto,
        SearchConversationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Conversation] = Conversation,
        query_dto: Type[QueryConversationDto] = QueryConversationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for_verification(
        self, verification_id: str, conversation_type: ConversationType
    ) -> Optional[Conversation]:
        """The single thread of a channel for a verification (§11.1 — one thread per channel)."""
        stmt = select(Conversation).where(
            and_(
                Conversation.deleted.is_(False),
                Conversation.verification_id == verification_id,
                Conversation.type == conversation_type.value,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_general_support(self, user_id: str) -> Optional[Conversation]:
        """The user's single *web* general-support thread (§N.2).

        Scoped to the web channel because a linked WhatsApp number's thread is also
        `GENERAL_SUPPORT` owned by the same account (§26.8) — without the filter both rows
        match and `/portal/support` could open the WhatsApp thread instead.
        """
        stmt = select(Conversation).where(
            and_(
                Conversation.deleted.is_(False),
                Conversation.type == ConversationType.GENERAL_SUPPORT.value,
                Conversation.channel == ConversationChannel.WEB.value,
                Conversation.created_by == user_id,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_by_ids(self, ids: List[str]) -> List[Conversation]:
        if not ids:
            return []
        stmt = (
            select(Conversation)
            .where(and_(Conversation.deleted.is_(False), Conversation.id.in_(ids)))
            .order_by(desc(Conversation.last_message_at))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_whatsapp_thread(self, phone: str) -> Optional[Conversation]:
        """The thread for a WhatsApp number, whether or not it belongs to an account yet.

        Keyed on the number rather than a user because an enquiry usually arrives before
        we know who is sending it (§26.4.3/§26.4.4).
        """
        stmt = select(Conversation).where(
            and_(
                Conversation.deleted.is_(False),
                Conversation.channel == ConversationChannel.WHATSAPP.value,
                Conversation.external_ref == phone,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    # ── Admin Conversations inbox (§16.5) ─────────────────────────────
    #
    # Admins are a shared inbox, not members, so every thread with a message is theirs to
    # work: the two verification threads, web support, and WhatsApp (Decision K). The page,
    # its total, the unpaged list and the Chat counter all read the same scope, and each
    # admin's read state comes from an outer join on their own participant row — one query
    # per page, never a lookup per thread.

    async def list_admin_inbox_page(
        self,
        admin_id: str,
        page: int,
        page_size: int,
        *,
        inbox_filter: Optional[AdminInboxFilter] = None,
        query: Optional[str] = None,
    ) -> Tuple[List[AdminInboxRow], int]:
        """One page of the inbox, newest activity first, with its total."""
        count_stmt = self._admin_inbox_where(
            select(func.count(Conversation.id)).select_from(Conversation).outerjoin(User, _owner_join()),
            inbox_filter, query,
        )
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        rows_stmt = (
            self._admin_inbox_where(self._admin_inbox_select(admin_id), inbox_filter, query)
            .order_by(desc(Conversation.last_message_at), desc(Conversation.id))
            .offset(page * page_size)
            .limit(page_size)
        )
        return await self._admin_inbox_rows(rows_stmt), total

    async def list_admin_inbox(self, admin_id: str) -> List[AdminInboxRow]:
        """The whole inbox, unpaged — the admin's answer to the member-facing
        `/chat/conversations` list, which predates the paged console endpoint."""
        stmt = self._admin_inbox_where(
            self._admin_inbox_select(admin_id), None, None
        ).order_by(desc(Conversation.last_message_at), desc(Conversation.id))
        return await self._admin_inbox_rows(stmt)

    async def count_admin_unread(self, admin_id: str) -> int:
        """The admin's Chat counter: inbox threads unread by *this* admin, by the same
        ``unread_condition`` the member counter uses."""
        stmt = self._admin_inbox_where(
            select(func.count(Conversation.id))
            .select_from(Conversation)
            .outerjoin(ConversationParticipant, _admin_membership_join(admin_id)),
            None, None,
        ).where(unread_condition())
        return int((await self._session.execute(stmt)).scalar() or 0)

    @staticmethod
    def _admin_inbox_select(admin_id: str):
        return (
            select(Conversation, ConversationParticipant, User.first_name, User.last_name, User.email)
            .select_from(Conversation)
            .outerjoin(ConversationParticipant, _admin_membership_join(admin_id))
            .outerjoin(User, _owner_join())
        )

    @staticmethod
    def _admin_inbox_where(stmt, inbox_filter: Optional[AdminInboxFilter], query: Optional[str]):
        conditions = [
            Conversation.deleted.is_(False),
            # A thread with no message yet (a support page opened and left) is nothing to work.
            Conversation.last_message_at.is_not(None),
        ]
        if inbox_filter == AdminInboxFilter.SUPPORT:
            conditions.append(Conversation.type == ConversationType.GENERAL_SUPPORT.value)
            conditions.append(Conversation.channel == ConversationChannel.WEB.value)
        elif inbox_filter == AdminInboxFilter.WHATSAPP:
            conditions.append(Conversation.channel == ConversationChannel.WHATSAPP.value)
        elif inbox_filter == AdminInboxFilter.CASES:
            conditions.append(Conversation.type.in_(_CASE_TYPES))
        if query and query.strip():
            like = f"%{query.strip()}%"
            conditions.append(
                or_(
                    Conversation.external_ref.ilike(like),
                    Conversation.subject.ilike(like),
                    func.concat(User.first_name, " ", User.last_name).ilike(like),
                    User.email.ilike(like),
                )
            )
        return stmt.where(and_(*conditions))

    async def _admin_inbox_rows(self, stmt) -> List[AdminInboxRow]:
        rows = (await self._session.execute(stmt)).all()
        return [
            AdminInboxRow(
                conversation=convo,
                membership=membership,
                owner_name=" ".join(part for part in (first_name, last_name) if part) or None,
                owner_email=email,
            )
            for convo, membership, first_name, last_name, email in rows
        ]


_CASE_TYPES = [ConversationType.CUSTOMER_ADMIN.value, ConversationType.ADMIN_AGENT.value]


@dataclass(frozen=True)
class AdminInboxRow:
    """One inbox thread with the viewing admin's own membership (None until they first open
    it) and, for a support thread, the account it belongs to."""

    conversation: Conversation
    membership: Optional[ConversationParticipant]
    owner_name: Optional[str]
    owner_email: Optional[str]


def _admin_membership_join(admin_id: str):
    return and_(
        joins_conversation(),
        ConversationParticipant.user_id == str(admin_id),
        ConversationParticipant.deleted.is_(False),
    )


def _owner_join():
    """The account behind a support thread — web support is opened by its customer, and a
    WhatsApp thread's ``created_by`` is its linked owner (§26.8). A case thread's opener is
    whoever got there first, often an admin, so it is not an owner and is not joined.
    ``users.id`` is a native UUID and ``created_by`` its string form, hence the cast on the
    users side (a stray non-UUID ``created_by`` must not fail the whole inbox)."""
    return and_(
        Conversation.type == ConversationType.GENERAL_SUPPORT.value,
        cast(User.id, String) == Conversation.created_by,
    )
