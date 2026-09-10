"""Conversation data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.communication.conversation.models import (
    Conversation,
    ConversationChannel,
    ConversationType,
    CreateConversationDto,
    QueryConversationDto,
    SearchConversationDto,
    UpdateConversationDto,
)
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
        """The user's single general-support thread (§N.2)."""
        stmt = select(Conversation).where(
            and_(
                Conversation.deleted.is_(False),
                Conversation.type == ConversationType.GENERAL_SUPPORT.value,
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

    async def list_admin_inbox_threads(self) -> List[Conversation]:
        """Every thread the admin console is responsible for (§N.3, §26.3.3).

        Two groups: verification-scoped threads (customer↔admin, admin↔agent) and every
        WhatsApp thread, which is mediated by an admin by definition (Decision K) even
        though it is not tied to a verification. Admins see all of them, not only the ones
        they have personally sent into.
        """
        stmt = (
            select(Conversation)
            .where(
                and_(
                    Conversation.deleted.is_(False),
                    Conversation.last_message_at.is_not(None),
                    or_(
                        Conversation.type.in_([
                            ConversationType.CUSTOMER_ADMIN.value,
                            ConversationType.ADMIN_AGENT.value,
                        ]),
                        Conversation.channel == ConversationChannel.WHATSAPP.value,
                    ),
                )
            )
            .order_by(desc(Conversation.last_message_at))
        )
        return list((await self._session.execute(stmt)).scalars().all())
