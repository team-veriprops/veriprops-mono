"""Data-erasure controllers (PRD §18.1, §19.1).

Self-service (data subject): /users/me/erasure-requests — the Account → Data & privacy
surface. Admin review: /admin/erasure-requests (RBAC MANAGE_COMPLIANCE, SUPER only).
Frontend services: frontend/src/components/{account,admin}/libs/erasure-service.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.compliance.erasure.models import (
    DataErasureRequestDto,
    RequestErasureDto,
    ResolveErasureDto,
    erasure_to_dto as _to_dto,
)
from main.app.domain.compliance.erasure.service import ErasureService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, SuccessResponse

erasure_router = APIRouter(prefix="/users/me/erasure-requests", tags=["Account: Data & Privacy"])
admin_erasure_router = APIRouter(prefix="/admin/erasure-requests", tags=["Admin: Data Erasure"])
erasure_service: ErasureService = di[ErasureService]

_guard = require_permission(Permission.MANAGE_COMPLIANCE)


# ── Self-service (data subject) ───────────────────────────────────

@erasure_router.post("", response_model=SuccessResponse[DataErasureRequestDto])
async def request_erasure(req: RequestErasureDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    row = await erasure_service.request(user_id, user_id, req.reason)
    return SuccessResponse[DataErasureRequestDto](data=_to_dto(row))


@erasure_router.get("", response_model=SuccessResponse[List[DataErasureRequestDto]])
async def my_erasure_requests(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    rows = await erasure_service.list_for_user(user_id)
    return SuccessResponse[List[DataErasureRequestDto]](data=[_to_dto(r) for r in rows])


# ── Admin review (MANAGE_COMPLIANCE — SUPER only) ─────────────────

@admin_erasure_router.get("", response_model=SuccessResponse[Page[DataErasureRequestDto]])
async def list_erasure_requests(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(_guard),
):
    return SuccessResponse[Page[DataErasureRequestDto]](
        data=await erasure_service.page(status, page, page_size)
    )


@admin_erasure_router.get("/{request_id}", response_model=SuccessResponse[DataErasureRequestDto])
async def get_erasure_request(request_id: str, _admin_id: str = Depends(_guard)):
    return SuccessResponse[DataErasureRequestDto](data=_to_dto(await erasure_service.get(request_id)))


@admin_erasure_router.post("/{request_id}/approve", response_model=SuccessResponse[DataErasureRequestDto])
async def approve_erasure(request_id: str, admin_id: str = Depends(_guard)):
    row = await erasure_service.approve(request_id, admin_id)
    return SuccessResponse[DataErasureRequestDto](data=_to_dto(row))


@admin_erasure_router.post("/{request_id}/reject", response_model=SuccessResponse[DataErasureRequestDto])
async def reject_erasure(request_id: str, req: ResolveErasureDto, admin_id: str = Depends(_guard)):
    row = await erasure_service.reject(request_id, admin_id, req.note)
    return SuccessResponse[DataErasureRequestDto](data=_to_dto(row))


@admin_erasure_router.post("/{request_id}/execute", response_model=SuccessResponse[DataErasureRequestDto])
async def execute_erasure(request_id: str, admin_id: str = Depends(_guard)):
    """Irreversibly pseudonymise the subject's PII (§4.11)."""
    row = await erasure_service.execute(request_id, admin_id)
    return SuccessResponse[DataErasureRequestDto](data=_to_dto(row))
