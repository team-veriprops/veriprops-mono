"""Trust score weight config endpoints — S30 (admin-configurable weights)."""
from __future__ import annotations

from typing import List

from fastapi import Depends

from main.app.domain.verification.scoring.models import SetTierWeightsDto, TrustScoreWeightDto
from main.app.domain.verification.scoring.service import TrustScoreService
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

scoring_router = AppRouter(prefix="/admin/trust-score-weights", tags=["Admin — Trust Score"])

_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])


@scoring_router.get("", response_model=SuccessResponse[List[TrustScoreWeightDto]])
async def list_weights(
    svc: TrustScoreService = Depends(lambda: __import__("kink", fromlist=["di"]).di[TrustScoreService]),
    _claims=Depends(_auth),
):
    weights = await svc.list_all_weights()
    return SuccessResponse.ok(weights)


@scoring_router.put("/{tier}", response_model=SuccessResponse[List[TrustScoreWeightDto]])
async def set_tier_weights(
    tier: str,
    body: SetTierWeightsDto,
    svc: TrustScoreService = Depends(lambda: __import__("kink", fromlist=["di"]).di[TrustScoreService]),
    claims=Depends(_auth),
):
    updated = await svc.update_weights(tier, body, admin_id=claims.sub)
    return SuccessResponse.ok(updated)
