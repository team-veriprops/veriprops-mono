"""Meta template registry admin controller (PRD §26.7, WA-15/WA-41).

URL shape: /admin/config/whatsapp-templates — RBAC-gated (CONFIGURE_SYSTEM). Frontend
service: frontend/src/components/admin/config/libs/whatsapp-template-service.

Read plus a sync action, and deliberately no write: template definitions are code-owned
(D59a) and approval status belongs to Meta, so there is nothing here for an admin to edit
that would mean anything.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.channel.whatsapp.template.models import (
    WhatsAppTemplateDto,
    WhatsAppTemplateSyncResultDto,
)
from main.app.domain.channel.whatsapp.template.service import WhatsAppTemplateService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

whatsapp_template_router = APIRouter(
    prefix="/admin/config/whatsapp-templates", tags=["Admin: WhatsApp Templates"]
)
whatsapp_template_service: WhatsAppTemplateService = di[WhatsAppTemplateService]


@whatsapp_template_router.get("", response_model=SuccessResponse[List[WhatsAppTemplateDto]])
async def list_templates(
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """The §26.7 set with Meta's latest verdict on each — the §26.11 launch-gate view."""
    return SuccessResponse[List[WhatsAppTemplateDto]](
        data=await whatsapp_template_service.list_all()
    )


@whatsapp_template_router.post(
    "/sync", response_model=SuccessResponse[WhatsAppTemplateSyncResultDto]
)
async def sync_templates(
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Ask the configured transport what Meta currently says about each template."""
    return SuccessResponse[WhatsAppTemplateSyncResultDto](
        data=await whatsapp_template_service.sync()
    )
