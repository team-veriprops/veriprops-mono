"""Customer report-sharing controller (PRD §13.2).

URL shape: /verifications/{id}/... — customer-owned (JWT subject must own the verification).
Frontend service: frontend/src/components/portal/libs/share-service.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.verification.share.models import (
    CreateShareRequestDto,
    PublicVisibilityDto,
    ShareDto,
)
from main.app.domain.verification.share.service import ShareService
from main.appodus_utils.db.models import SuccessResponse

share_router = APIRouter(prefix="/verifications", tags=["Verification Report Sharing"])
share_service: ShareService = di[ShareService]


@share_router.get(
    "/{verification_id}/shares", response_model=SuccessResponse[List[ShareDto]]
)
async def list_shares(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    shares = await share_service.list_shares(verification_id, customer_id)
    return SuccessResponse[List[ShareDto]](data=shares)


@share_router.post(
    "/{verification_id}/shares", response_model=SuccessResponse[ShareDto]
)
async def create_share(
    verification_id: str, req: CreateShareRequestDto, authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    share = await share_service.create_share(verification_id, customer_id, req)
    return SuccessResponse[ShareDto](data=share)


@share_router.post(
    "/{verification_id}/shares/{share_id}/revoke", response_model=SuccessResponse[ShareDto]
)
async def revoke_share(verification_id: str, share_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    share = await share_service.revoke_share(verification_id, share_id, customer_id)
    return SuccessResponse[ShareDto](data=share)


@share_router.put(
    "/{verification_id}/public-visibility", response_model=SuccessResponse[PublicVisibilityDto]
)
async def set_public_visibility(
    verification_id: str, req: PublicVisibilityDto, authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    enabled = await share_service.set_public_visibility(verification_id, customer_id, req.enabled)
    return SuccessResponse[PublicVisibilityDto](data=PublicVisibilityDto(enabled=enabled))
