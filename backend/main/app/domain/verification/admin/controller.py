"""Admin verification HTTP routes — PRD Phase 6 (R6.1, R6.2, R6.5).

URL shape: /api/admin/verifications/...

All endpoints require MANAGE_VERIFICATIONS permission.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.verification.admin.models import (
    AddNoteDto,
    AdminFailDto,
    AdminVerificationDetailDto,
    AdminVerificationListItemDto,
    SetDelayDto,
    UpdateNoteDto,
    VerificationNoteDto,
)
from main.app.domain.verification.admin.service import AdminVerificationService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, SuccessResponse

admin_verification_service: AdminVerificationService = di[AdminVerificationService]

admin_verification_router = APIRouter(prefix="/admin/verifications", tags=["Admin Verifications"])


@admin_verification_router.get(
    "",
    response_model=Page[AdminVerificationListItemDto],
)
async def list_verifications(
    status: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None),
    vid: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return await admin_verification_service.list_verifications(
        status=status,
        tier=tier,
        state=state,
        lga=lga,
        vid=vid,
        page=page,
        page_size=page_size,
    )


@admin_verification_router.get(
    "/{vid}",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def get_verification(
    vid: str,
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.get_detail(vid)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/pause",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def pause_verification(
    vid: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.pause(vid, admin_id)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/resume",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def resume_verification(
    vid: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.resume(vid, admin_id)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/cancel",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def cancel_verification(
    vid: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.cancel(vid, admin_id)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/fail",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def fail_verification(
    vid: str,
    req: AdminFailDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.fail(vid, admin_id, req.reason)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/delay",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def set_delay(
    vid: str,
    req: SetDelayDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.set_delay(vid, admin_id, req)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)


@admin_verification_router.post(
    "/{vid}/notes",
    response_model=SuccessResponse[VerificationNoteDto],
)
async def add_note(
    vid: str,
    req: AddNoteDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.add_note(vid, admin_id, req)
    return SuccessResponse[VerificationNoteDto](data=dto)


@admin_verification_router.put(
    "/{vid}/notes/{note_id}",
    response_model=SuccessResponse[VerificationNoteDto],
)
async def update_note(
    vid: str,
    note_id: str,
    req: UpdateNoteDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.update_note(vid, note_id, admin_id, req)
    return SuccessResponse[VerificationNoteDto](data=dto)


@admin_verification_router.post(
    "/{vid}/release-to-pool",
    response_model=SuccessResponse[AdminVerificationDetailDto],
)
async def release_to_pool(
    vid: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    dto = await admin_verification_service.release_to_pool(vid, admin_id)
    return SuccessResponse[AdminVerificationDetailDto](data=dto)
