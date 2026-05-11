"""Admin config HTTP routes — GET /api/admin/config, PUT /api/admin/config/{key}."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.admin_config.models import AdminConfigDto, SetAdminConfigDto
from main.app.domain.admin_config.service import AdminConfigService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

admin_config_service: AdminConfigService = di[AdminConfigService]

admin_config_router = APIRouter(prefix="/admin/config", tags=["Admin Config"])


@admin_config_router.get("", response_model=SuccessResponse[List[AdminConfigDto]])
async def list_config(
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    items = await admin_config_service.get_all()
    return SuccessResponse[List[AdminConfigDto]](data=items)


@admin_config_router.put("/{key}", response_model=SuccessResponse[AdminConfigDto])
async def set_config(
    key: str,
    req: SetAdminConfigDto,
    admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    dto = await admin_config_service.set(key, req.value, admin_id)
    return SuccessResponse[AdminConfigDto](data=dto)
