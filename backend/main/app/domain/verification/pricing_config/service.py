"""Pricing config service (PRD §18.1, D36).

The admin-editable source of truth for per-tier NGN prices + their itemized line items.
``tier_price_kobo`` is the single resolver every pricing path reads (quote/submit/recheck/
upgrade), falling back to the static seed defaults so a missing row never breaks a caller.
Edits take effect on the next quote — the exit criterion for Phase 18 (no deploy needed).
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.core.state.status import VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.pricing import is_upgrade, price_ngn_kobo, upgrade_delta_kobo
from main.app.domain.verification.pricing_config.line_item.models import (
    CreatePricingLineItemDto,
    PricingLineItem,
    PricingLineItemDto,
)
from main.app.domain.verification.pricing_config.line_item.repo import PricingLineItemRepo
from main.app.domain.verification.pricing_config.models import (
    CreatePricingTierConfigDto,
    LineItemInputDto,
    PricingTierConfig,
    PricingTierDto,
    TierPricingViewDto,
    UpdatePricingTierConfigDto,
    UpgradeDeltaDto,
)
from main.app.domain.verification.pricing_config.repo import PricingTierConfigRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PricingConfigService:
    def __init__(
        self,
        tier_repo: PricingTierConfigRepo,
        line_item_repo: PricingLineItemRepo,
        audit_service: AuditLogService,
    ):
        self._tiers = tier_repo
        self._line_items = line_item_repo
        self._audit = audit_service

    async def tier_price_kobo(self, tier: VerificationTier) -> int:
        """The live contractual NGN price for a tier, in kobo — the single resolver every
        pricing path reads. Falls back to the static default if unconfigured."""
        row = await self._tiers.get_for_tier(tier.value)
        return row.price_ngn_kobo if row is not None else price_ngn_kobo(tier)

    async def view(self) -> TierPricingViewDto:
        """The full admin pricing view: every tier's price + line items + upgrade deltas."""
        tiers = [await self._tier_dto(tier) for tier in VerificationTier]
        deltas: List[UpgradeDeltaDto] = []
        for current in VerificationTier:
            for target in VerificationTier:
                if is_upgrade(current, target):
                    delta = upgrade_delta_kobo(
                        await self.tier_price_kobo(current), await self.tier_price_kobo(target)
                    )
                    deltas.append(UpgradeDeltaDto(from_tier=current, to_tier=target, delta_minor=delta))
        return TierPricingViewDto(tiers=tiers, upgrade_deltas=deltas)

    async def set_tier_price(self, tier: VerificationTier, price_minor: int, admin_id: str) -> PricingTierConfig:
        existing = await self._tiers.get_for_tier(tier.value)
        if existing is None:
            row = await self._tiers.create_return_model(CreatePricingTierConfigDto(
                tier=tier.value, price_ngn_kobo=price_minor,
            ))
        else:
            await self._tiers.update(existing.id, UpdatePricingTierConfigDto(price_ngn_kobo=price_minor))
            row = await self._tiers.get_model(existing.id)
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="pricing_tier_config", resource_id=row.id, actor_id=admin_id,
            details={"tier": tier.value, "price_ngn_kobo": price_minor},
        )
        return row

    async def set_line_items(
        self, tier: VerificationTier, items: List[LineItemInputDto], admin_id: str
    ) -> List[PricingLineItem]:
        """Replace a tier's line items (§18.1). Soft-deletes the old set, writes the new one."""
        for existing in await self._line_items.list_for_tier(tier.value):
            await self._line_items.soft_delete(existing.id)
        written: List[PricingLineItem] = []
        for order, item in enumerate(items):
            written.append(await self._line_items.create_return_model(CreatePricingLineItemDto(
                tier=tier.value, label=item.label, amount_minor=item.amount_minor, sort_order=order,
            )))
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="pricing_line_items", resource_id=tier.value, actor_id=admin_id,
            details={"tier": tier.value, "count": len(items)},
        )
        return written

    # ── helpers ───────────────────────────────────────────────────

    async def _tier_dto(self, tier: VerificationTier) -> PricingTierDto:
        return PricingTierDto(
            tier=tier,
            price_ngn_minor=await self.tier_price_kobo(tier),
            line_items=[self._line_item_dto(li) for li in await self._line_items.list_for_tier(tier.value)],
        )

    @staticmethod
    def _line_item_dto(li: PricingLineItem) -> PricingLineItemDto:
        return PricingLineItemDto(
            id=li.id, tier=li.tier, label=li.label, amount_minor=li.amount_minor,
            sort_order=li.sort_order or 0, date_created=li.date_created,
        )
