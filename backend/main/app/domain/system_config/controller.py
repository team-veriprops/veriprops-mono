"""System configuration admin controller (PRD §14, §18.5 / D28).

URL shape: /admin/config/settings — RBAC-gated (CONFIGURE_SYSTEM). Frontend service:
frontend/src/components/admin/config/libs/system-config-service.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.system_config.models import (
    ConfigKey,
    SetConfigValueDto,
    SystemConfigDto,
)
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

system_config_router = APIRouter(prefix="/admin/config/settings", tags=["Admin: System Config"])
config_service: ConfigService = di[ConfigService]


@system_config_router.get("", response_model=SuccessResponse[List[SystemConfigDto]])
async def list_settings(_admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM))):
    return SuccessResponse[List[SystemConfigDto]](data=await config_service.list_all())


@system_config_router.put("/{key}", response_model=SuccessResponse[List[SystemConfigDto]])
async def set_setting(
    key: ConfigKey,
    req: SetConfigValueDto,
    admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    await config_service.set(key, req.value, admin_id)
    return SuccessResponse[List[SystemConfigDto]](data=await config_service.list_all())
