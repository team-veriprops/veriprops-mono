"""Chat message data access."""
from __future__ import annotations

from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.chat_message.models import (
    ChatMessage,
    CreateChatMessageDto,
    QueryChatMessageDto,
    SearchChatMessageDto,
    UpdateChatMessageDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo


@inject
class ChatMessageRepo(
    GenericRepo[
        ChatMessage,
        CreateChatMessageDto,
        UpdateChatMessageDto,
        QueryChatMessageDto,
        SearchChatMessageDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ChatMessage] = ChatMessage,
        query_dto: Type[QueryChatMessageDto] = QueryChatMessageDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_delivered_page(
        self, conversation_id: str, viewer_id: Optional[str], page: int, page_size: int
    ) -> Tuple[List[ChatMessage], int]:
        """Thread messages a viewer may see: everything DELIVERED, plus the viewer's own
        still-HELD messages (so a sender sees their message pending review, §11.2).

        Returns ``(rows, total)`` — the service converts rows to DTOs before paginating, so
        ORM models never reach ``build_page`` (which validates its items as DTOs)."""
        offset = page * page_size
        conversation_id = Utils.uuid_to_hex(conversation_id)
        viewer_id = str(viewer_id) if viewer_id is not None else None
        base = and_(
            ChatMessage.deleted.is_(False),
            ChatMessage.conversation_id == conversation_id,
        )
        if viewer_id is not None:
            visible = ChatMessage.state == ChatMessageState.DELIVERED.value
            own_held = and_(
                ChatMessage.sender_user_id == viewer_id,
                ChatMessage.state.in_(
                    [ChatMessageState.HELD.value, ChatMessageState.PENDING_SCAN.value]
                ),
            )
            where = and_(base, visible.self_group() | own_held.self_group())
        else:
            where = and_(base, ChatMessage.state == ChatMessageState.DELIVERED.value)

        total = int((await self._session.execute(
            select(func.count(ChatMessage.id)).where(where)
        )).scalar() or 0)

        stmt = (
            select(ChatMessage)
            .where(where)
            .order_by(asc(ChatMessage.date_created))
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def list_held_page(self, page: int, page_size: int) -> Tuple[List[ChatMessage], int]:
        """The admin hold-review queue (§11.2) — oldest-held first. Returns ``(rows, total)``."""
        offset = page * page_size
        where = and_(
            ChatMessage.deleted.is_(False),
            ChatMessage.state == ChatMessageState.HELD.value,
        )
        total = await self.held_count()
        stmt = (
            select(ChatMessage)
            .where(where)
            .order_by(asc(ChatMessage.held_at))
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def held_count(self) -> int:
        where = and_(
            ChatMessage.deleted.is_(False),
            ChatMessage.state == ChatMessageState.HELD.value,
        )
        return int((await self._session.execute(
            select(func.count(ChatMessage.id)).where(where)
        )).scalar() or 0)

    async def latest_delivered(self, conversation_id: str) -> Optional[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.deleted.is_(False),
                    ChatMessage.conversation_id == Utils.uuid_to_hex(conversation_id),
                    ChatMessage.state == ChatMessageState.DELIVERED.value,
                )
            )
            .order_by(desc(ChatMessage.date_created))
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()
