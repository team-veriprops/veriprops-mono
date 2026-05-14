"""Content controllers — S55.

Admin router: /admin/content  (VIEW_ADMIN_PANEL / CREATE_CONTENT / PUBLISH_CONTENT)
Public router: /public/content (no auth, published_only=True)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, Query
from kink import di

from main.app.domain.content.models import (
    ContentItemDto,
    ContentItemType,
    CreateContentItemDto,
    PublishContentItemDto,
    ReorderContentItemDto,
    UpdateContentItemDto,
)
from main.app.domain.content.service import ContentService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.db.models import Page
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

content_admin_router = AppRouter(prefix="/admin/content", tags=["Content"])
public_content_router = AppRouter(prefix="/public/content", tags=["Public Content"])

_view_auth = AuthJWTBearer(required_permissions=["VIEW_ADMIN_PANEL"])
_create_auth = AuthJWTBearer(required_permissions=["CREATE_CONTENT"])
_publish_auth = AuthJWTBearer(required_permissions=["PUBLISH_CONTENT"])


# ── Admin endpoints ───────────────────────────────────────────────

@content_admin_router.get("", response_model=Page[ContentItemDto])
async def admin_list_content(
    item_type: Optional[str] = Query(None),
    published_only: Optional[bool] = Query(None),
    page: int = Query(0, ge=0),
    page_size: int = Query(25, ge=1, le=100),
    _: JWTClaims = Depends(_view_auth),
):
    svc: ContentService = di[ContentService]
    return await svc.list_admin(item_type=item_type, published_only=published_only, page=page, page_size=page_size)


@content_admin_router.post("", response_model=SuccessResponse[ContentItemDto])
async def create_content(dto: CreateContentItemDto, claims: JWTClaims = Depends(_create_auth)):
    svc: ContentService = di[ContentService]
    result = await svc.create(dto, claims.sub)
    return SuccessResponse.ok(result)


@content_admin_router.put("/{item_id}", response_model=SuccessResponse[ContentItemDto])
async def update_content(
    item_id: str,
    dto: UpdateContentItemDto,
    claims: JWTClaims = Depends(_create_auth),
):
    svc: ContentService = di[ContentService]
    result = await svc.update(item_id, dto, claims.sub)
    return SuccessResponse.ok(result)


@content_admin_router.post("/{item_id}/publish", response_model=SuccessResponse[ContentItemDto])
async def publish_content(
    item_id: str,
    dto: PublishContentItemDto,
    claims: JWTClaims = Depends(_publish_auth),
):
    svc: ContentService = di[ContentService]
    result = await svc.publish(item_id, dto.is_published, claims.sub)
    return SuccessResponse.ok(result)


@content_admin_router.delete("/{item_id}", response_model=SuccessResponse[bool])
async def delete_content(item_id: str, claims: JWTClaims = Depends(_publish_auth)):
    svc: ContentService = di[ContentService]
    await svc.delete(item_id, claims.sub)
    return SuccessResponse.ok(True)


@content_admin_router.post("/reorder", response_model=SuccessResponse[List[ContentItemDto]])
async def reorder_content(dto: ReorderContentItemDto, claims: JWTClaims = Depends(_publish_auth)):
    svc: ContentService = di[ContentService]
    result = await svc.reorder(dto, claims.sub)
    return SuccessResponse.ok(result)


# ── Public endpoints ──────────────────────────────────────────────

@public_content_router.get("/how-it-works", response_model=SuccessResponse[List[ContentItemDto]])
async def public_how_it_works():
    svc: ContentService = di[ContentService]
    items = await svc.list_by_type(ContentItemType.HOW_IT_WORKS_STEP)
    return SuccessResponse.ok(items)


@public_content_router.get("/faqs", response_model=SuccessResponse[List[ContentItemDto]])
async def public_faqs():
    svc: ContentService = di[ContentService]
    items = await svc.list_by_type(ContentItemType.FAQ)
    return SuccessResponse.ok(items)


@public_content_router.get("/testimonials", response_model=SuccessResponse[List[ContentItemDto]])
async def public_testimonials():
    svc: ContentService = di[ContentService]
    items = await svc.list_by_type(ContentItemType.TESTIMONIAL)
    return SuccessResponse.ok(items)


@public_content_router.get("/agent-spotlights", response_model=SuccessResponse[List[ContentItemDto]])
async def public_agent_spotlights():
    svc: ContentService = di[ContentService]
    items = await svc.list_by_type(ContentItemType.AGENT_SPOTLIGHT)
    return SuccessResponse.ok(items)


@public_content_router.get("/area-insights", response_model=SuccessResponse[List[ContentItemDto]])
async def public_area_insights(
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None),
):
    svc: ContentService = di[ContentService]
    items = await svc.list_area_insights(state=state, lga=lga, published_only=True)
    return SuccessResponse.ok(items)
