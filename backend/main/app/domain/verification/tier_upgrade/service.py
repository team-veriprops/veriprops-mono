"""Tier upgrade service — S45."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.models import VerificationStatus, VerificationTier, UpdateVerificationDto
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.tier_upgrade.models import (
    CreateTierUpgradeDto,
    SubmitTierUpgradeDto,
    TierUpgradeDto,
    TierUpgradePreviewDto,
    TierUpgradeStatus,
    UpdateTierUpgradeDto,
    SearchTierUpgradeDto,
)
from main.app.domain.verification.tier_upgrade.repo import TierUpgradeRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]

# Fallback base prices (minor units, NGN) per tier if pricing service unavailable
_TIER_PRICES = {
    "BASIC": 15000_00,
    "STANDARD": 35000_00,
    "PREMIUM": 75000_00,
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class TierUpgradeService:
    def __init__(self, repo: TierUpgradeRepo, ver_repo: VerificationRepo):
        self._repo = repo
        self._ver_repo = ver_repo

    async def preview(self, verification_id: str) -> TierUpgradePreviewDto:
        ver = await self._ver_repo.get_model(verification_id)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        from_tier = ver.tier.upper()
        to_tier = self._next_tier(from_tier)
        if to_tier is None:
            raise ValidationException(message="Already at highest tier")
        delta = self._compute_delta(from_tier, to_tier)
        return TierUpgradePreviewDto(from_tier=from_tier, to_tier=to_tier, delta_price=delta)

    async def submit(
        self, verification_id: str, customer_id: str, dto: SubmitTierUpgradeDto,
    ) -> TierUpgradeDto:
        ver = await self._ver_repo.get_model(verification_id)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")

        current_status = VerificationStatus(ver.status)
        if current_status not in (VerificationStatus.COMPLETED, VerificationStatus.IN_PROGRESS):
            raise ValidationException(message="Tier upgrade only available on COMPLETED or IN_PROGRESS verifications")

        from_tier = ver.tier.upper()
        to_tier = dto.to_tier.upper()
        if from_tier == to_tier:
            raise ValidationException(message="Already at requested tier")

        # Idempotency: return existing PENDING upgrade for same (verification_id, to_tier)
        existing = await self._repo.get_all(SearchTierUpgradeDto(
            verification_id=verification_id, status=TierUpgradeStatus.PENDING.value
        ))
        for ex in existing:
            if ex.to_tier == to_tier:
                return self._to_dto(ex)

        delta = self._compute_delta(from_tier, to_tier)
        row = await self._repo.create(CreateTierUpgradeDto(
            verification_id=verification_id,
            from_tier=from_tier,
            to_tier=to_tier,
            delta_price=delta,
            status=TierUpgradeStatus.PENDING.value,
            requested_by=customer_id,
        ))
        return self._to_dto(row)

    async def complete(self, upgrade_id: str, payment_id: str) -> TierUpgradeDto:
        row = await self._repo.get_model(upgrade_id)
        if row is None:
            raise ResourceNotFoundException(resource="TierUpgrade")

        await self._repo.update(upgrade_id, UpdateTierUpgradeDto(
            status=TierUpgradeStatus.COMPLETED.value,
            payment_id=payment_id,
        ))

        ver = await self._ver_repo.get_model(str(row.verification_id))
        if ver:
            await self._ver_repo.update(str(ver.id), UpdateVerificationDto(tier=VerificationTier(row.to_tier)))
            if VerificationStatus(ver.status) == VerificationStatus.COMPLETED:
                from main.app.domain.verification.service import VerificationService
                ver_svc: VerificationService = di[VerificationService]
                await ver_svc.transition(str(ver.id), VerificationStatus.IN_PROGRESS, actor_id=None)

        return self._to_dto(await self._repo.get_model(upgrade_id))

    @staticmethod
    def _next_tier(current: str) -> str | None:
        order = ["BASIC", "STANDARD", "PREMIUM"]
        idx = order.index(current) if current in order else -1
        return order[idx + 1] if idx < len(order) - 1 else None

    @staticmethod
    def _compute_delta(from_tier: str, to_tier: str) -> float:
        return max(0.0, (_TIER_PRICES.get(to_tier, 0) - _TIER_PRICES.get(from_tier, 0)) / 100)

    def _to_dto(self, row) -> TierUpgradeDto:
        return TierUpgradeDto(
            id=str(row.id),
            verification_id=str(row.verification_id),
            from_tier=row.from_tier,
            to_tier=row.to_tier,
            delta_price=float(row.delta_price) if row.delta_price else None,
            status=TierUpgradeStatus(row.status),
            requested_by=str(row.requested_by),
            payment_id=str(row.payment_id) if row.payment_id else None,
            date_created=str(row.date_created),
        )
