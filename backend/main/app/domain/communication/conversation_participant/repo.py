"""Conversation participant data access — read state + Chat unread counter (§N.3)."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.communication.conversation.models import Conversation
from main.app.domain.communication.conversation_participant.models import (
    ConversationParticipant,
    CreateConversationParticipantDto,
    QueryConversationParticipantDto,
    SearchConversationParticipantDto,
    UpdateConversationParticipantDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo


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

    async def unread_conversation_count(self, user_id: str) -> int:
        """Number of the user's conversations with unread messages (§N.3 Chat counter).

        Unread = the thread has a ``last_message_at`` newer than the participant's
        ``last_read_at`` (a never-opened thread with any message counts as unread).
        """
        p = ConversationParticipant
        c = Conversation
        stmt = (
            select(func.count())
            .select_from(p)
            .join(c, c.id == p.conversation_id)
            .where(
                and_(
                    p.deleted.is_(False),
                    c.deleted.is_(False),
                    p.user_id == user_id,
                    c.last_message_at.is_not(None),
                    or_(p.last_read_at.is_(None), p.last_read_at < c.last_message_at),
                )
            )
        )
        return int((await self._session.execute(stmt)).scalar() or 0)
