"""Notification REST endpoints — S39, S41."""
from __future__ import annotations

from typing import List

from fastapi import Depends

from main.app.domain.notification.models import (
    NotificationDto,
    NotificationPreferenceDto,
    UpsertNotificationPreferenceDto,
)
from main.app.domain.notification.service import NotificationService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

notification_router = AppRouter(prefix="/notifications", tags=["Notifications"])

_auth = AuthJWTBearer()


@notification_router.get("", response_model=SuccessResponse[List[NotificationDto]])
async def list_notifications(
    limit: int = 30,
    claims: JWTClaims = Depends(_auth),
):
    svc: NotificationService = di[NotificationService]
    items = await svc.list_for_recipient(claims.sub, limit=limit)
    return SuccessResponse.ok(items)


@notification_router.post("/{notification_id}/read", response_model=SuccessResponse[None])
async def mark_read(
    notification_id: str,
    claims: JWTClaims = Depends(_auth),
):
    svc: NotificationService = di[NotificationService]
    await svc.mark_read(notification_id, claims.sub)
    return SuccessResponse.ok(None)


@notification_router.get("/preferences", response_model=SuccessResponse[List[NotificationPreferenceDto]])
async def get_preferences(claims: JWTClaims = Depends(_auth)):
    svc: NotificationService = di[NotificationService]
    prefs = await svc.get_preferences(claims.sub)
    return SuccessResponse.ok(prefs)


@notification_router.put("/preferences", response_model=SuccessResponse[NotificationPreferenceDto])
async def upsert_preference(
    dto: UpsertNotificationPreferenceDto,
    claims: JWTClaims = Depends(_auth),
):
    svc: NotificationService = di[NotificationService]
    pref = await svc.upsert_preference(claims.sub, dto)
    return SuccessResponse.ok(pref)
