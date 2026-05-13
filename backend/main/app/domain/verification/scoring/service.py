"""Trust score computation service — S30.

Computes a 0–100 composite trust score from approved task scores using
tier-specific weights. Weights are admin-configurable; defaults seeded by migration.
Score recomputes on every task approval. Audit trail stored per computation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, TYPE_CHECKING

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.scoring.models import (
    CreateBreakdownDto,
    CreateWeightConfigDto,
    SetTierWeightsDto,
    TrustScoreWeightDto,
    UpdateWeightDto,
)
from main.app.domain.verification.scoring.repo import (
    TrustScoreBreakdownRepo,
    TrustScoreWeightRepo,
)
from main.app.domain.verification.task.models import TaskRole, TaskStatus
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]

# Default weights seeded by migration (must sum to 100 per tier)
_DEFAULT_WEIGHTS: Dict[str, Dict[str, Decimal]] = {
    "BASIC": {
        TaskRole.REGISTRY.value: Decimal("100"),
    },
    "STANDARD": {
        TaskRole.FIELD.value: Decimal("35"),
        TaskRole.SURVEYOR.value: Decimal("30"),
        TaskRole.REGISTRY.value: Decimal("35"),
    },
    "PREMIUM": {
        TaskRole.FIELD.value: Decimal("25"),
        TaskRole.SURVEYOR.value: Decimal("20"),
        TaskRole.REGISTRY.value: Decimal("30"),
        TaskRole.LAWYER.value: Decimal("25"),
    },
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TrustScoreService:
    def __init__(
        self,
        weight_repo: TrustScoreWeightRepo,
        breakdown_repo: TrustScoreBreakdownRepo,
        audit: AuditLogService,
    ):
        self._weights = weight_repo
        self._breakdowns = breakdown_repo
        self._audit = audit

    async def get_weights(self, tier: str) -> Dict[str, Decimal]:
        """Return {role: weight} for the given tier, falling back to defaults."""
        rows = await self._weights.list_for_tier(tier.upper())
        if not rows:
            return dict(_DEFAULT_WEIGHTS.get(tier.upper(), {}))
        return {row.role: Decimal(str(row.weight)) for row in rows}

    async def list_all_weights(self) -> List[TrustScoreWeightDto]:
        rows = await self._weights.list_all()
        return [self._weight_to_dto(r) for r in rows]

    async def recompute_for_verification(
        self,
        verification_id: str,
        tier: str,
    ) -> Decimal:
        """Recompute and persist trust score from all APPROVED tasks' trust_score values."""
        from main.app.domain.verification.task.repo import TaskRepo
        task_repo: TaskRepo = di[TaskRepo]
        tasks = await task_repo.list_for_verification(verification_id)

        approved = [t for t in tasks if t.status == TaskStatus.APPROVED.value]
        weights = await self.get_weights(tier)

        task_scores: Dict[str, Decimal] = {}
        for task in approved:
            score = task.trust_score if task.trust_score is not None else 0
            task_scores[task.role] = Decimal(str(score))

        # Weighted mean: only roles that have a weight; 0 for missing roles
        total_weight = Decimal("0")
        weighted_sum = Decimal("0")
        for role, weight in weights.items():
            total_weight += weight
            weighted_sum += weight * task_scores.get(role, Decimal("0"))

        computed = (
            (weighted_sum / total_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if total_weight > 0
            else Decimal("0")
        )

        await self._save_breakdown(
            verification_id=verification_id,
            task_scores=task_scores,
            weights=weights,
            score=computed,
        )

        # Persist trust_score on the verification row itself
        from main.app.domain.verification.repo import VerificationRepo
        from main.app.domain.verification.models import UpdateVerificationDto
        ver_repo: VerificationRepo = di[VerificationRepo]
        await ver_repo.update(
            verification_id,
            UpdateVerificationDto(trust_score=computed),
        )

        logger.info(f"Trust score for {verification_id}: {computed} (tier={tier})")
        return computed

    async def update_weights(
        self,
        tier: str,
        payload: SetTierWeightsDto,
        admin_id: str,
    ) -> List[TrustScoreWeightDto]:
        """Replace all weights for the given tier. Validates sum == 100."""
        total = sum(payload.weights.values())
        if abs(total - Decimal("100")) > Decimal("0.01"):
            raise ValidationException(
                message=f"Weights for tier {tier} must sum to 100 (got {total})"
            )

        results = []
        for role, weight in payload.weights.items():
            existing = await self._weights.get_for_tier_role(tier.upper(), role.upper())
            if existing:
                await self._weights.update(
                    str(existing.id),
                    UpdateWeightDto(weight=weight, updated_by=admin_id),
                )
                row = await self._weights.get_for_tier_role(tier.upper(), role.upper())
            else:
                row = await self._weights.create_return_model(
                    CreateWeightConfigDto(
                        tier=tier.upper(),
                        role=role.upper(),
                        weight=weight,
                        updated_by=admin_id,
                    )
                )
            results.append(self._weight_to_dto(row))

        self._audit.schedule(
            AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="TrustScoreWeightConfig",
            resource_id=tier.upper(),
            actor_id=admin_id,
            meta={"tier": tier, "weights": {r: str(w) for r, w in payload.weights.items()}},
        )
        return results

    # ── helpers ───────────────────────────────────────────────────────

    async def _save_breakdown(
        self,
        verification_id: str,
        task_scores: Dict[str, Decimal],
        weights: Dict[str, Decimal],
        score: Decimal,
    ) -> None:
        await self._breakdowns.create_return_model(
            CreateBreakdownDto(
                verification_id=verification_id,
                task_scores_json=json.dumps({k: str(v) for k, v in task_scores.items()}),
                weights_json=json.dumps({k: str(v) for k, v in weights.items()}),
                computed_score=score,
                computed_at=datetime.now(timezone.utc),
            )
        )

    @staticmethod
    def _weight_to_dto(row) -> TrustScoreWeightDto:
        return TrustScoreWeightDto(
            id=str(row.id),
            tier=row.tier,
            role=row.role,
            weight=Decimal(str(row.weight)),
            updated_by=row.updated_by,
            date_updated=row.date_updated,
        )
