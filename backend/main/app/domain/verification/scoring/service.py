"""Trust Score Weights service (PRD §8.3, D14).

Owns the admin weight config (per tier × role, summing to 100% within a tier) and the
deterministic composite computation used by the release gate. Default weights
(``DEFAULT_TRUST_WEIGHTS`` in models.py) are seeded by migration 0001; admins edit them via
the CRUD, enforcing the sum-to-100 invariant so a released score is always a true 0–100 blend.
"""
from __future__ import annotations

from typing import Dict, List

from kink import inject

from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.scoring.models import (
    CreateTrustWeightDto,
    TrustScoreWeight,
    UpdateTrustWeightDto,
)
from main.app.domain.verification.scoring.repo import TrustScoreWeightRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

_FULL_PERCENT = 100


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TrustScoreWeightService:
    def __init__(self, weight_repo: TrustScoreWeightRepo, audit_service: AuditLogService):
        self._weight_repo = weight_repo
        self._audit = audit_service

    async def list_all(self) -> List[TrustScoreWeight]:
        return await self._weight_repo.list_all()

    async def list_for_tier(self, tier: VerificationTier) -> List[TrustScoreWeight]:
        return await self._weight_repo.list_for_tier(tier.value)

    async def set_tier_weights(
        self, tier: VerificationTier, weights: Dict[AgentRole, int], admin_id: str
    ) -> List[TrustScoreWeight]:
        """Replace a tier's weight map (§8.3). Enforces exactly the tier's roles and a
        sum of 100; upserts each role weight; audited."""
        required = set(roles_for_tier(tier))
        provided = {AgentRole(r) for r in weights}
        if provided != required:
            raise ValidationException(
                message=f"{tier.value} weights must cover exactly {sorted(r.value for r in required)}."
            )
        total = sum(weights.values())
        if total != _FULL_PERCENT:
            raise ValidationException(
                message=f"{tier.value} weights must sum to 100 (got {total})."
            )
        for role, weight in weights.items():
            if weight < 0:
                raise ValidationException(message="Weights cannot be negative.")
            existing = await self._weight_repo.get_for_tier_role(tier.value, role.value)
            if existing is None:
                await self._weight_repo.create_return_model(CreateTrustWeightDto(
                    tier=tier, role=role, weight_percent=weight,
                ))
            else:
                await self._weight_repo.update(existing.id, UpdateTrustWeightDto(weight_percent=weight))
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="trust_score_weight_config", resource_id=tier.value, actor_id=admin_id,
            details={"tier": tier.value, "weights": {r.value: w for r, w in weights.items()}},
        )
        return await self._weight_repo.list_for_tier(tier.value)

    async def compute_composite(
        self, tier: VerificationTier, role_quality: Dict[AgentRole, int]
    ) -> int:
        """Composite trust score (0–100) = Σ (weight_role/100 × quality_role) over the
        tier's roles (§8.3). Deterministic; called only at release (§8.6)."""
        weights = {AgentRole(w.role): w.weight_percent for w in await self._weight_repo.list_for_tier(tier.value)}
        score = 0.0
        for role in roles_for_tier(tier):
            weight = weights.get(role, 0)
            quality = role_quality.get(role, 0)
            score += (weight / _FULL_PERCENT) * quality
        return round(score)
