"""Trust Score Weights admin controller (PRD §8.3, §18.5 / D14).

URL shape: /admin/trust-score-weights/... — RBAC-gated (MANAGE_VERIFICATIONS).
Frontend service: frontend/src/components/admin/verifications/libs/trust-weight-service.
"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from kink import di

from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.scoring.models import (
    SetTierWeightsDto,
    TierWeightsDto,
    TrustScoreWeight,
    TrustWeightDto,
)
from main.app.domain.verification.scoring.service import TrustScoreWeightService
from main.appodus_utils.db.models import SuccessResponse

trust_weight_router = APIRouter(prefix="/admin/trust-score-weights", tags=["Admin: Trust Score Weights"])
weight_service: TrustScoreWeightService = di[TrustScoreWeightService]


def _weight_dto(w: TrustScoreWeight) -> TrustWeightDto:
    return TrustWeightDto(
        id=w.id, tier=VerificationTier(w.tier), role=AgentRole(w.role),
        weight_percent=w.weight_percent, date_created=w.date_created,
    )


def _tier_dto(tier: VerificationTier, weights: List[TrustScoreWeight]) -> TierWeightsDto:
    ordered = {AgentRole(w.role): w for w in weights}
    dtos = [_weight_dto(ordered[r]) for r in roles_for_tier(tier) if r in ordered]
    total = sum(w.weight_percent for w in dtos)
    return TierWeightsDto(tier=tier, weights=dtos, total_percent=total, valid=total == 100)


@trust_weight_router.get("", response_model=SuccessResponse[List[TierWeightsDto]])
async def list_weights(_admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS))):
    all_weights = await weight_service.list_all()
    by_tier: Dict[str, List[TrustScoreWeight]] = {}
    for w in all_weights:
        by_tier.setdefault(w.tier, []).append(w)
    return SuccessResponse[List[TierWeightsDto]](data=[
        _tier_dto(tier, by_tier.get(tier.value, [])) for tier in VerificationTier
    ])


@trust_weight_router.put("/{tier}", response_model=SuccessResponse[TierWeightsDto])
async def set_tier_weights(
    tier: VerificationTier,
    req: SetTierWeightsDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    weights = await weight_service.set_tier_weights(tier, req.weights, admin_id)
    return SuccessResponse[TierWeightsDto](data=_tier_dto(tier, weights))
