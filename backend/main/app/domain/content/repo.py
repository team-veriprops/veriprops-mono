"""Content repo — S55."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.content.models import (
    ContentItem,
    ContentItemType,
    CreateContentItemDto,
    QueryContentItemDto,
    SearchContentItemDto,
    UpdateContentItemDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class ContentItemRepo(
    GenericRepo[
        ContentItem,
        CreateContentItemDto,
        UpdateContentItemDto,
        QueryContentItemDto,
        SearchContentItemDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ContentItem] = ContentItem,
        query_dto: Type[QueryContentItemDto] = QueryContentItemDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_by_type(
        self,
        item_type: ContentItemType,
        published_only: bool = True,
    ) -> List[ContentItem]:
        session = self._session
        filters = [
            ContentItem.item_type == item_type.value,
            ContentItem.deleted == False,
        ]
        if published_only:
            filters.append(ContentItem.is_published == True)
        result = await session.execute(
            select(ContentItem).where(*filters).order_by(ContentItem.sort_order)
        )
        return list(result.scalars().all())

    async def list_area_insights(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        published_only: bool = True,
    ) -> List[ContentItem]:
        session = self._session
        filters = [
            ContentItem.item_type == ContentItemType.AREA_INSIGHT.value,
            ContentItem.deleted == False,
        ]
        if published_only:
            filters.append(ContentItem.is_published == True)
        if state:
            filters.append(ContentItem.state == state)
        if lga:
            filters.append(ContentItem.lga == lga)
        result = await session.execute(
            select(ContentItem).where(*filters).order_by(ContentItem.state, ContentItem.lga, ContentItem.sort_order)
        )
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Optional[ContentItem]:
        session = self._session
        result = await session.execute(
            select(ContentItem).where(
                ContentItem.slug == slug,
                ContentItem.deleted == False,
            ).limit(1)
        )
        return result.scalars().first()

    async def list_admin(
        self,
        item_type: Optional[str] = None,
        published_only: Optional[bool] = None,
        page: int = 0,
        page_size: int = 25,
    ):
        from sqlalchemy import func
        session = self._session
        filters = [ContentItem.deleted == False]
        if item_type:
            filters.append(ContentItem.item_type == item_type)
        if published_only is not None:
            filters.append(ContentItem.is_published == published_only)
        total = await session.scalar(select(func.count(ContentItem.id)).where(*filters)) or 0
        offset = page * page_size
        result = await session.execute(
            select(ContentItem).where(*filters).order_by(ContentItem.item_type, ContentItem.sort_order)
            .offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), int(total)
