"""Notification preferences controller (PRD §12.4). URL shape: /notification-preferences/...

Per-event email/SMS opt-out. In-app can never be disabled (§12.1), so it is not exposed here;
which events and channels a user may change comes from `catalogue.py`.
Frontend service: frontend/src/components/notifications/libs/notification-service.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

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
    """Every event the caller may change, in page order — the catalogue is the backend's."""
    await authorize.jwt_required()
    user_id, user_type, personas = _caller(authorize)
    return SuccessResponse[List[PreferenceDto]](data=await service.list_for_user(user_id, user_type, personas))


@notification_preference_router.put("", response_model=SuccessResponse[PreferenceDto])
async def set_preference(req: SetPreferenceDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id, user_type, personas = _caller(authorize)
    return SuccessResponse[PreferenceDto](data=await service.set(user_id, user_type, personas, req))


def _caller(authorize: AuthJWT) -> Tuple[str, Optional[str], List[str]]:
    """The caller's id, account type and personas, from the server-signed session claims."""
    claims = authorize.get_raw_jwt() or {}
    return str(authorize.get_jwt_subject()), claims.get("user_type"), list(claims.get("personas") or [])
