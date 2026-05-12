"""Dispute endpoints — S46."""
from __future__ import annotations

from typing import List

from fastapi import Depends

from main.app.domain.verification.dispute.models import (
    DisputeDto,
    DisputeResolutionDto,
    ResolveDisputeDto,
    SubmitDisputeDto,
)
from main.app.domain.verification.dispute.service import DisputeService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

dispute_router = AppRouter(tags=["Disputes"])

_auth = AuthJWTBearer()
_admin_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])


@dispute_router.post(
    "/portal/verifications/{vid}/dispute",
    response_model=SuccessResponse[DisputeDto],
)
async def submit_dispute(
    vid: str, dto: SubmitDisputeDto, claims: JWTClaims = Depends(_auth)
):
    svc: DisputeService = di[DisputeService]
    result = await svc.submit(vid, claims.sub, dto)
    return SuccessResponse.ok(result)


@dispute_router.get(
    "/admin/disputes",
    response_model=SuccessResponse[List[DisputeDto]],
)
async def list_disputes(claims: JWTClaims = Depends(_admin_auth)):
    svc: DisputeService = di[DisputeService]
    items = await svc.list_pending()
    return SuccessResponse.ok(items)


@dispute_router.post(
    "/admin/disputes/{dispute_id}/resolve",
    response_model=SuccessResponse[DisputeResolutionDto],
)
async def resolve_dispute(
    dispute_id: str, dto: ResolveDisputeDto, claims: JWTClaims = Depends(_admin_auth)
):
    svc: DisputeService = di[DisputeService]
    result = await svc.resolve(dispute_id, claims.sub, dto)
    return SuccessResponse.ok(result)
