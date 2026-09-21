"""Conversation participant data access — read state + Chat unread counter (§N.3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import String, Uuid, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.communication.conversation_participant.models import (
    ConversationParticipant,
    CreateConversationParticipantDto,
    QueryConversationParticipantDto,
    SearchConversationParticipantDto,
    UpdateConversationParticipantDto,
)
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import User
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo


def unread_condition():
    """The SQL twin of ``conversation_participant.models.is_unread`` — change both together.

    Reads ``Conversation`` joined to ``ConversationParticipant``. The thread's
    ``last_message_at`` is capped at the participant's ``visible_until`` and ignored when it
    predates ``visible_from``, so a released WhatsApp thread stops badging and a freshly
    linked one does not light up for messages hidden from them. Every term tolerates a
    missing participant row (an outer join), which reads as never opened: unread.
    """
    p = ConversationParticipant
    c = Conversation
    effective_last = func.least(c.last_message_at, func.coalesce(p.visible_until, c.last_message_at))
    return and_(
        c.last_message_at.is_not(None),
        or_(p.visible_from.is_(None), effective_last >= p.visible_from),
        or_(p.last_read_at.is_(None), p.last_read_at < effective_last),
    )


def joins_conversation():
    """Join condition from a participant row to its thread.

    ``conversation_id`` is stored as the conversation's .hex (32-char, no hyphens) while
    ``Conversation.id`` is a native UUID — cast the ref back to UUID to join (a bare
    ``c.id == p.conversation_id`` raises "operator does not exist: uuid = varchar").
    """
    return Conversation.id == cast(ConversationParticipant.conversation_id, Uuid)


@inject
class ConversationParticipantRepo(
    GenericRepo[
        ConversationParticipant,
        CreateConversationParticipantDto,
        UpdateConversationParticipantDto,
        QueryConversationParticipantDto,
        SearchConversationParticipantDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ConversationParticipant] = ConversationParticipant,
        query_dto: Type[QueryConversationParticipantDto] = QueryConversationParticipantDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for(self, conversation_id: str, user_id: str) -> Optional[ConversationParticipant]:
        # Reference columns are String(36). Entity ids travel as `.hex` (32-char, the DTO
        # wire form) while user ids are `str(uuid)` (36-char, the JWT form) — coerce each to
        # its canonical string so a freshly-created entity's `uuid.UUID` matches the stored ref.
        stmt = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.deleted.is_(False),
                ConversationParticipant.conversation_id == Utils.uuid_to_hex(conversation_id),
                ConversationParticipant.user_id == str(user_id),
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_user(self, user_id: str) -> List[ConversationParticipant]:
        stmt = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.deleted.is_(False),
                ConversationParticipant.user_id == user_id,
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_conversation(self, conversation_id: str) -> List[ConversationParticipant]:
        stmt = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.deleted.is_(False),
                ConversationParticipant.conversation_id == Utils.uuid_to_hex(conversation_id),
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def latest_admin_read_at(self, conversation_id: str) -> Optional[datetime]:
        """When any admin last read the thread — "seen by support" for its customer.

        Admins are a shared inbox, so it is the latest read by *any* admin. Admin rows carry
        no participant role, so admin-ness comes from the account itself.
        """
        p = ConversationParticipant
        stmt = (
            select(func.max(p.last_read_at))
            .select_from(p)
            .join(User, cast(User.id, String) == p.user_id)
            .where(
                and_(
                    p.deleted.is_(False),
                    p.conversation_id == Utils.uuid_to_hex(conversation_id),
                    User.user_type == UserType.ADMIN.value,
                )
            )
        )
        return (await self._session.execute(stmt)).scalar()

    async def unread_conversation_count(self, user_id: str) -> int:
        """Number of the user's conversations with unread messages (§N.3 Chat counter),
        by the shared ``unread_condition``."""
        p = ConversationParticipant
        c = Conversation
        stmt = (
            select(func.count())
            .select_from(p)
            .join(c, joins_conversation())
            .where(
                and_(
                    p.deleted.is_(False),
                    c.deleted.is_(False),
                    p.user_id == user_id,
                    unread_condition(),
                )
            )
        )
        return int((await self._session.execute(stmt)).scalar() or 0)
