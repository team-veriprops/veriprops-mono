"""Broadcast controller — S55."""
from __future__ import annotations

from fastapi import Depends, Query
from kink import di

from main.app.domain.broadcast.models import (
    BroadcastDto,
    CreateBroadcastDto,
    PreviewBroadcastDto,
    ScheduleBroadcastDto,
    UpdateBroadcastDto,
)
from main.app.domain.broadcast.service import BroadcastService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.db.models import Page
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

broadcast_router = AppRouter(prefix="/admin/broadcasts", tags=["Broadcasts"])

_auth = AuthJWTBearer(required_permissions=["PUBLISH_CONTENT"])


@broadcast_router.get("", response_model=Page[BroadcastDto])
async def list_broadcasts(
    page: int = Query(0, ge=0),
    page_size: int = Query(25, ge=1, le=100),
    _: JWTClaims = Depends(_auth),
):
    svc: BroadcastService = di[BroadcastService]
    return await svc.list_broadcasts(page=page, page_size=page_size)


@broadcast_router.post("", response_model=SuccessResponse[BroadcastDto])
async def create_broadcast(dto: CreateBroadcastDto, claims: JWTClaims = Depends(_auth)):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.create(dto, claims.sub)
    return SuccessResponse.ok(result)


@broadcast_router.put("/{broadcast_id}", response_model=SuccessResponse[BroadcastDto])
async def update_broadcast(
    broadcast_id: str,
    dto: UpdateBroadcastDto,
    claims: JWTClaims = Depends(_auth),
):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.update(broadcast_id, dto, claims.sub)
    return SuccessResponse.ok(result)


@broadcast_router.post("/{broadcast_id}/schedule", response_model=SuccessResponse[BroadcastDto])
async def schedule_broadcast(
    broadcast_id: str,
    dto: ScheduleBroadcastDto,
    claims: JWTClaims = Depends(_auth),
):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.schedule(broadcast_id, dto, claims.sub)
    return SuccessResponse.ok(result)


@broadcast_router.post("/{broadcast_id}/send-now", response_model=SuccessResponse[BroadcastDto])
async def send_broadcast_now(broadcast_id: str, claims: JWTClaims = Depends(_auth)):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.send_now(broadcast_id, claims.sub)
    return SuccessResponse.ok(result)


@broadcast_router.post("/{broadcast_id}/cancel", response_model=SuccessResponse[BroadcastDto])
async def cancel_broadcast(broadcast_id: str, claims: JWTClaims = Depends(_auth)):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.cancel(broadcast_id, claims.sub)
    return SuccessResponse.ok(result)


@broadcast_router.get("/{broadcast_id}/preview", response_model=SuccessResponse[PreviewBroadcastDto])
async def preview_broadcast(broadcast_id: str, _: JWTClaims = Depends(_auth)):
    svc: BroadcastService = di[BroadcastService]
    result = await svc.preview(broadcast_id)
    return SuccessResponse.ok(result)
