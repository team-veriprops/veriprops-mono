"""Broadcast admin controller (PRD §18.1, D37).

URL shape: /admin/broadcasts — RBAC-gated (BROADCAST). Frontend service:
frontend/src/components/admin/broadcasts/libs/broadcast-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.broadcast.models import (
    Broadcast,
    BroadcastAudience,
    BroadcastDto,
    BroadcastPreviewDto,
    BroadcastStatus,
    ComposeBroadcastDto,
)
from main.app.domain.broadcast.service import BroadcastService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, PaginationMeta, SuccessResponse

broadcast_router = APIRouter(prefix="/admin/broadcasts", tags=["Admin: Broadcasts"])
broadcast_service: BroadcastService = di[BroadcastService]
_guard = require_permission(Permission.BROADCAST)


def _dto(b: Broadcast) -> BroadcastDto:
    return BroadcastDto(
        id=b.id, audience=BroadcastAudience(b.audience), subject=b.subject, body=b.body,
        status=BroadcastStatus(b.status), scheduled_at=b.scheduled_at, sent_at=b.sent_at,
        recipient_count=b.recipient_count or 0, date_created=b.date_created,
    )


@broadcast_router.get("", response_model=SuccessResponse[Page[BroadcastDto]])
async def list_broadcasts(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    status: str | None = Query(default=None),
    _admin_id: str = Depends(_guard),
):
    rows, total = await broadcast_service.list_page(page, page_size, status)
    data = Page[BroadcastDto](
        items=[_dto(b) for b in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total_items=total),
    )
    return SuccessResponse[Page[BroadcastDto]](data=data)


@broadcast_router.get("/preview", response_model=SuccessResponse[BroadcastPreviewDto])
async def preview_broadcast(audience: BroadcastAudience = Query(...), _admin_id: str = Depends(_guard)):
    return SuccessResponse[BroadcastPreviewDto](data=await broadcast_service.preview(audience))


@broadcast_router.post("", response_model=SuccessResponse[BroadcastDto])
async def compose_broadcast(req: ComposeBroadcastDto, admin_id: str = Depends(_guard)):
    return SuccessResponse[BroadcastDto](data=_dto(await broadcast_service.compose(req, admin_id)))


@broadcast_router.get("/{broadcast_id}", response_model=SuccessResponse[BroadcastDto])
async def get_broadcast(broadcast_id: str, _admin_id: str = Depends(_guard)):
    return SuccessResponse[BroadcastDto](data=_dto(await broadcast_service.get(broadcast_id)))


@broadcast_router.post("/{broadcast_id}/send", response_model=SuccessResponse[BroadcastDto])
async def send_broadcast(broadcast_id: str, admin_id: str = Depends(_guard)):
    return SuccessResponse[BroadcastDto](data=_dto(await broadcast_service.send_now(broadcast_id, admin_id)))


@broadcast_router.post("/{broadcast_id}/cancel", response_model=SuccessResponse[BroadcastDto])
async def cancel_broadcast(broadcast_id: str, admin_id: str = Depends(_guard)):
    return SuccessResponse[BroadcastDto](data=_dto(await broadcast_service.cancel(broadcast_id, admin_id)))


@broadcast_router.post("/sweeps/scheduled", response_model=SuccessResponse[dict])
async def sweep_scheduled(_admin_id: str = Depends(_guard)):
    """Send scheduled broadcasts whose time has passed (§18.1). Runs on a schedule in
    non-test envs; this endpoint triggers it on demand (idempotent)."""
    sent = await broadcast_service.sweep_scheduled_broadcasts()
    return SuccessResponse[dict](data={"sent": sent})
