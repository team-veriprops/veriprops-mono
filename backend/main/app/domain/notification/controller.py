"""Notifications controller (PRD §12, §N.4). URL shape: /notifications/...

The in-app feed, the unread counter, and mark-read. Delivery is over the per-user SSE
stream (`GET /chat/stream`, §4.9); this is the durable history + counter surface.
Frontend service: frontend/src/components/notifications/libs/notification-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.notification.models import NotificationDto
from main.app.domain.notification.service import NotificationService
from main.appodus_utils.db.models import Page, SuccessResponse

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])
service: NotificationService = di[NotificationService]


@notification_router.get("", response_model=SuccessResponse[Page[NotificationDto]])
async def list_notifications(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[Page[NotificationDto]](data=await service.feed(user_id, page, page_size))


@notification_router.get("/unread", response_model=SuccessResponse[dict])
async def unread_count(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[dict](data={"count": await service.unread_count(user_id)})


@notification_router.post("/{notification_id}/read", response_model=SuccessResponse[dict])
async def mark_read(notification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    await service.mark_read(notification_id, user_id)
    return SuccessResponse[dict](data={"count": await service.unread_count(user_id)})


@notification_router.post("/read-all", response_model=SuccessResponse[dict])
async def mark_all_read(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    updated = await service.mark_all_read(user_id)
    return SuccessResponse[dict](data={"updated": updated, "count": await service.unread_count(user_id)})
