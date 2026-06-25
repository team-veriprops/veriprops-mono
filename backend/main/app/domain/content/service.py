"""Content service — S55."""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.domain.content.models import (
    ContentItem,
    ContentItemDto,
    ContentItemType,
    CreateContentItemDto,
    ReorderContentItemDto,
    UpdateContentItemDto,
)
from main.app.domain.content.repo import ContentItemRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ContentService:
    def __init__(self, repo: ContentItemRepo):
        self._repo = repo

    async def list_by_type(
        self,
        item_type: ContentItemType,
        published_only: bool = True,
    ) -> List[ContentItemDto]:
        rows = await self._repo.list_by_type(item_type, published_only)
        return [self._to_dto(r) for r in rows]

    async def list_area_insights(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        published_only: bool = True,
    ) -> List[ContentItemDto]:
        rows = await self._repo.list_area_insights(state, lga, published_only)
        return [self._to_dto(r) for r in rows]

    async def list_admin(
        self,
        item_type: Optional[str] = None,
        published_only: Optional[bool] = None,
        page: int = 0,
        page_size: int = 25,
    ) -> Page[ContentItemDto]:
        rows, total = await self._repo.list_admin(item_type, published_only, page, page_size)
        items = [self._to_dto(r) for r in rows]
        meta = PaginationMeta(page=page, page_size=page_size, count=len(items), total=total)
        return Page[ContentItemDto](items=items, meta=meta)

    async def get(self, item_id: str) -> ContentItemDto:
        row = await self._repo.get_model(item_id)
        if row is None:
            raise ResourceNotFoundException(resource="ContentItem")
        return self._to_dto(row)

    async def create(self, dto: CreateContentItemDto, author_id: str) -> ContentItemDto:
        existing = await self._repo.get_by_slug(dto.slug)
        if existing is not None:
            raise ValidationException(message=f"Slug already in use: {dto.slug}")
        create_dto = CreateContentItemDto(**{**dto.model_dump(), "author_id": author_id})
        result = await self._repo.create(create_dto)
        row = await self._repo.get_model(result.data.id)
        return self._to_dto(row)

    async def update(self, item_id: str, dto: UpdateContentItemDto, author_id: str) -> ContentItemDto:
        row = await self._repo.get_model(item_id)
        if row is None:
            raise ResourceNotFoundException(resource="ContentItem")
        if dto.slug and dto.slug != row.slug:
            existing = await self._repo.get_by_slug(dto.slug)
            if existing is not None:
                raise ValidationException(message=f"Slug already in use: {dto.slug}")
        await self._repo.update(item_id, dto)
        updated = await self._repo.get_model(item_id)
        return self._to_dto(updated)

    async def publish(self, item_id: str, is_published: bool, admin_id: str) -> ContentItemDto:
        row = await self._repo.get_model(item_id)
        if row is None:
            raise ResourceNotFoundException(resource="ContentItem")
        await self._repo.update(item_id, UpdateContentItemDto(is_published=is_published))
        updated = await self._repo.get_model(item_id)
        return self._to_dto(updated)

    async def delete(self, item_id: str, admin_id: str) -> None:
        row = await self._repo.get_model(item_id)
        if row is None:
            raise ResourceNotFoundException(resource="ContentItem")
        row.deleted = True
        row.date_updated = Utils.datetime_now()

    async def reorder(self, dto: ReorderContentItemDto, admin_id: str) -> List[ContentItemDto]:
        for sort_order, item_id in enumerate(dto.item_ids):
            row = await self._repo.get_model(item_id)
            if row is not None:
                await self._repo.update(item_id, UpdateContentItemDto(sort_order=sort_order))
        rows = []
        for item_id in dto.item_ids:
            row = await self._repo.get_model(item_id)
            if row is not None:
                rows.append(self._to_dto(row))
        return rows

    @staticmethod
    def _to_dto(row: ContentItem) -> ContentItemDto:
        return ContentItemDto(
            id=str(row.id),
            item_type=ContentItemType(row.item_type),
            slug=row.slug,
            title=row.title,
            body=row.body,
            details=row.details,
            is_published=row.is_published,
            sort_order=row.sort_order,
            author_id=row.author_id,
            lga=row.lga,
            state=row.state,
            date_created=row.date_created,
            date_updated=row.date_updated,
        )
