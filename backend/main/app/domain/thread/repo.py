"""Thread & message repositories (S37)."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.thread.models import (
    CreateThreadDto,
    CreateThreadMessageDto,
    MessageThread,
    QueryThreadDto,
    QueryThreadMessageDto,
    SearchThreadDto,
    SearchThreadMessageDto,
    ThreadMessage,
    ThreadType,
    UpdateThreadMessageDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ThreadRepo(
    GenericRepo[
        MessageThread,
        CreateThreadDto,
        QueryThreadDto,
        QueryThreadDto,
        SearchThreadDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[MessageThread] = MessageThread,
        query_dto: Type[QueryThreadDto] = QueryThreadDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_by_verification_and_type(
        self, verification_id: str, thread_type: ThreadType
    ) -> Optional[MessageThread]:
        stmt = (
            select(MessageThread)
            .where(
                MessageThread.deleted.is_(False),
                MessageThread.verification_id == verification_id,
                MessageThread.thread_type == thread_type.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task(
        self, task_id: str, thread_type: ThreadType
    ) -> Optional[MessageThread]:
        stmt = (
            select(MessageThread)
            .where(
                MessageThread.deleted.is_(False),
                MessageThread.task_id == task_id,
                MessageThread.thread_type == thread_type.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[MessageThread]:
        stmt = (
            select(MessageThread)
            .where(
                MessageThread.deleted.is_(False),
                MessageThread.verification_id == verification_id,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class ThreadMessageRepo(
    GenericRepo[
        ThreadMessage,
        CreateThreadMessageDto,
        UpdateThreadMessageDto,
        QueryThreadMessageDto,
        SearchThreadMessageDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ThreadMessage] = ThreadMessage,
        query_dto: Type[QueryThreadMessageDto] = QueryThreadMessageDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_thread(
        self, thread_id: str, limit: int = 50, before_id: Optional[str] = None
    ) -> List[ThreadMessage]:
        stmt = (
            select(ThreadMessage)
            .where(
                ThreadMessage.deleted.is_(False),
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.is_held.is_(False),
            )
            .order_by(ThreadMessage.date_created.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_held(self) -> List[ThreadMessage]:
        stmt = (
            select(ThreadMessage)
            .where(
                ThreadMessage.deleted.is_(False),
                ThreadMessage.is_held.is_(True),
            )
            .order_by(ThreadMessage.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
