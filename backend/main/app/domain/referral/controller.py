"""Referral controller (PRD §17.1). URL shape: /referrals/...

Frontend service: frontend/src/components/portal/referrals/libs/referral-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.referral.models import ReferralSummaryDto
from main.app.domain.referral.service import ReferralService
from main.appodus_utils.db.models import SuccessResponse

referral_router = APIRouter(prefix="/referrals", tags=["Referrals"])
referral_service: ReferralService = di[ReferralService]


@referral_router.get("/me", response_model=SuccessResponse[ReferralSummaryDto])
async def get_my_referral(authorize: AuthJWT = Depends()):
    """The signed-in user's referral link + credit balances (§17.1 dashboard card)."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[ReferralSummaryDto](data=await referral_service.summary(user_id))
