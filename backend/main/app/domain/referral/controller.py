"""Referral HTTP routes — Phase 17 (S51).

URL shape: /api/referrals/...
All routes require JWT auth (customer persona).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.referral.models import (
    ClaimReferralDto,
    ReferralCodeDto,
    ReferralStatsDto,
)
from main.app.domain.referral.service import ReferralService
from main.appodus_utils.db.models import SuccessResponse

referral_service: ReferralService = di[ReferralService]

referral_router = APIRouter(prefix="/referrals", tags=["Referrals"])


@referral_router.get("/my-code", response_model=SuccessResponse[ReferralCodeDto])
async def get_my_referral_code(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await referral_service.get_or_create_code(user_id)
    return SuccessResponse[ReferralCodeDto](data=dto)


@referral_router.get("/my-stats", response_model=SuccessResponse[ReferralStatsDto])
async def get_my_referral_stats(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await referral_service.get_my_stats(user_id)
    return SuccessResponse[ReferralStatsDto](data=dto)


@referral_router.post("/claim", response_model=SuccessResponse[dict])
async def claim_referral(req: ClaimReferralDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    await referral_service.claim_referral(user_id, req)
    return SuccessResponse[dict](data={"claimed": True})
