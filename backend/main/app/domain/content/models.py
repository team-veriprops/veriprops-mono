"""Content domain models — S55 Phase 18.

CMS for site content: how-it-works steps, FAQs, testimonials, agent spotlights,
and area insights (admin-only per D21).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, Integer, String, Text, Index

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class ContentItemType(str, enum.Enum):
    HOW_IT_WORKS_STEP = "HOW_IT_WORKS_STEP"
    FAQ = "FAQ"
    TESTIMONIAL = "TESTIMONIAL"
    AGENT_SPOTLIGHT = "AGENT_SPOTLIGHT"
    AREA_INSIGHT = "AREA_INSIGHT"


class ContentItem(BaseEntity):
    __tablename__ = "content_items"

    item_type = Column(String(32), nullable=False, index=True)
    slug = Column(String(128), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    body = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    author_id = Column(String(36), nullable=True)
    lga = Column(String(128), nullable=True)
    state = Column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_content_items_type_published", "item_type", "is_published"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────


class ContentItemDto(Object):
    id: str
    item_type: ContentItemType
    slug: str
    title: str
    body: str
    meta: Optional[str] = None
    is_published: bool
    sort_order: int
    author_id: Optional[str] = None
    lga: Optional[str] = None
    state: Optional[str] = None
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateContentItemDto(Object):
    item_type: ContentItemType
    slug: str
    title: str
    body: str
    meta: Optional[str] = None
    is_published: bool = False
    sort_order: int = 0
    author_id: Optional[str] = None
    lga: Optional[str] = None
    state: Optional[str] = None


class UpdateContentItemDto(Object):
    slug: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    meta: Optional[str] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None
    lga: Optional[str] = None
    state: Optional[str] = None


class QueryContentItemDto(BaseQueryDto):
    item_type: Optional[str] = None
    is_published: Optional[bool] = None
    state: Optional[str] = None
    lga: Optional[str] = None


class SearchContentItemDto(PageRequest, BaseQueryDto):
    item_type: Optional[str] = None
    is_published: Optional[bool] = None
    state: Optional[str] = None
    lga: Optional[str] = None


class PublishContentItemDto(Object):
    is_published: bool


class ReorderContentItemDto(Object):
    item_ids: List[str]
