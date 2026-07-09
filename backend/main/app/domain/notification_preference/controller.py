"""Notification preferences controller (PRD §12.4). URL shape: /notification-preferences/...

Per-event email/SMS opt-out. In-app can never be disabled (§12.1), so it is not exposed here.
Frontend service: frontend/src/components/notifications/libs/notification-service.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.notification_preference.models import PreferenceDto, SetPreferenceDto
from main.app.domain.notification_preference.service import NotificationPreferenceService
from main.appodus_utils.db.models import SuccessResponse

notification_preference_router = APIRouter(
    prefix="/notification-preferences", tags=["Notification Preferences"]
)
service: NotificationPreferenceService = di[NotificationPreferenceService]


@notification_preference_router.get("", response_model=SuccessResponse[List[PreferenceDto]])
async def list_preferences(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[List[PreferenceDto]](data=await service.list_for_user(user_id))


@notification_preference_router.put("", response_model=SuccessResponse[PreferenceDto])
async def set_preference(req: SetPreferenceDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[PreferenceDto](data=await service.set(user_id, req))
