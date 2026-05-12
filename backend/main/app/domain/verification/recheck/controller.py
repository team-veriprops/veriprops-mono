"""Re-check endpoints — S44."""
from __future__ import annotations

from typing import List

from fastapi import Depends

from main.app.domain.verification.recheck.models import (
    RecheckRequestDto,
    ReviewRecheckDto,
    SubmitRecheckDto,
)
from main.app.domain.verification.recheck.service import RecheckService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

recheck_router = AppRouter(tags=["Re-check"])

_auth = AuthJWTBearer()
_admin_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])


@recheck_router.post("/portal/verifications/{vid}/recheck", response_model=SuccessResponse[RecheckRequestDto])
async def submit_recheck(
    vid: str,
    dto: SubmitRecheckDto,
    claims: JWTClaims = Depends(_auth),
):
    svc: RecheckService = di[RecheckService]
    result = await svc.submit(vid, claims.sub, dto)
    return SuccessResponse.ok(result)


@recheck_router.get("/admin/rechecks", response_model=SuccessResponse[List[RecheckRequestDto]])
async def list_rechecks(claims: JWTClaims = Depends(_admin_auth)):
    svc: RecheckService = di[RecheckService]
    items = await svc.list_pending()
    return SuccessResponse.ok(items)


@recheck_router.post("/admin/rechecks/{request_id}/approve", response_model=SuccessResponse[RecheckRequestDto])
async def approve_recheck(
    request_id: str,
    claims: JWTClaims = Depends(_admin_auth),
):
    svc: RecheckService = di[RecheckService]
    result = await svc.approve(request_id, claims.sub)
    return SuccessResponse.ok(result)


@recheck_router.post("/admin/rechecks/{request_id}/reject", response_model=SuccessResponse[RecheckRequestDto])
async def reject_recheck(
    request_id: str,
    dto: ReviewRecheckDto,
    claims: JWTClaims = Depends(_admin_auth),
):
    svc: RecheckService = di[RecheckService]
    result = await svc.reject(request_id, claims.sub, dto)
    return SuccessResponse.ok(result)
