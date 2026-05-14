"""Data retention & erasure endpoints — PRD Phase 19 (S58)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.retention.models import ErasureRequestDto, ErasureRequestPageDto
from main.app.domain.retention.service import RetentionPolicyService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ForbiddenException

retention_router = APIRouter(tags=["Data Retention — S58"])
retention_svc: RetentionPolicyService = di[RetentionPolicyService]


# ── Customer: submit / view erasure request ────────────────────────

@retention_router.post(
    "/account/erasure-request",
    response_model=SuccessResponse[ErasureRequestDto],
)
async def request_erasure(
    body: _ErasureRequestBody,
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    dto = await retention_svc.request_erasure(user_id, body.reason)
    return SuccessResponse.ok(dto)


@retention_router.get(
    "/account/erasure-request",
    response_model=SuccessResponse[Optional[ErasureRequestDto]],
)
async def get_my_erasure_request(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    dto = await retention_svc.get_latest_for_user(user_id)
    return SuccessResponse.ok(dto)


# ── Admin: list / approve / reject / execute ───────────────────────

@retention_router.get(
    "/admin/erasure-requests",
    response_model=SuccessResponse[ErasureRequestPageDto],
)
async def list_erasure_requests(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    result = await retention_svc.list_requests(status=status, page=page, page_size=page_size)
    return SuccessResponse.ok(result)


@retention_router.put(
    "/admin/erasure-requests/{request_id}/approve",
    response_model=SuccessResponse[ErasureRequestDto],
)
async def approve_erasure(
    request_id: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    dto = await retention_svc.approve_erasure(request_id, admin_id)
    return SuccessResponse.ok(dto)


@retention_router.put(
    "/admin/erasure-requests/{request_id}/reject",
    response_model=SuccessResponse[ErasureRequestDto],
)
async def reject_erasure(
    request_id: str,
    body: _RejectBody,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    dto = await retention_svc.reject_erasure(request_id, admin_id, body.rejection_reason)
    return SuccessResponse.ok(dto)


@retention_router.post(
    "/admin/erasure-requests/{request_id}/execute",
    response_model=SuccessResponse[None],
)
async def execute_erasure(
    request_id: str,
    admin_id: str = Depends(require_permission(Permission.MANAGE_USERS)),
):
    await retention_svc.execute_erasure(request_id, admin_id)
    return SuccessResponse.ok(None)


# ─── Request bodies ────────────────────────────────────────────────

from main.appodus_utils import Object  # noqa: E402


class _ErasureRequestBody(Object):
    reason: Optional[str] = None


class _RejectBody(Object):
    rejection_reason: str
