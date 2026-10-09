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
from main.app.domain.commission_rule.margin import CommissionMarginGuard
from main.app.domain.verification.pricing import effective_tier_price, is_upgrade, upgrade_delta_kobo
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
    UpgradeDeltaDto,
)
from main.app.domain.verification.pricing_config.repo import PricingTierConfigRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.db.locks import advisory_xact_lock
from main.appodus_utils.exception.exceptions import ValidationException

# Advisory-lock namespace: one replacement of a tier's line items at a time.
_LINE_ITEMS_LOCK = "pricing_line_items"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PricingConfigService:
    def __init__(
        self,
        tier_repo: PricingTierConfigRepo,
        line_item_repo: PricingLineItemRepo,
        audit_service: AuditLogService,
        commission_margin_guard: CommissionMarginGuard,
    ):
        self._tiers = tier_repo
        self._line_items = line_item_repo
        self._audit = audit_service
        self._margin_guard = commission_margin_guard

    async def tier_price_kobo(self, tier: VerificationTier) -> int:
        """The live contractual NGN price for a tier, in kobo — the single resolver every
        pricing path reads. Falls back to the static default if unconfigured."""
        row = await self._tiers.get_for_tier(tier.value)
        return effective_tier_price(row.price_ngn_kobo if row is not None else None, tier)

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

    async def set_tier_pricing(
        self, tier: VerificationTier, price_minor: int, items: List[LineItemInputDto], admin_id: str
    ) -> PricingTierConfig:
        """Set a tier's live price and replace its itemised breakdown, as one edit (§18.1).

        Saved apart, a price change left the breakdown customers see adding up to the old price,
        so the items, when there are any, must add up to the new one. Refused when the tier's
        agent commissions would then leave less than the minimum margin (§20.1 / D97).

        Two saves of one tier take turns (the margin lock, then the tier's own): interleaved,
        each would soft-delete the old items and leave both new sets live.
        """
        self._validate_pricing(price_minor, items)
        await self._margin_guard.check(price_overrides={tier: price_minor})
        await advisory_xact_lock(f"{_LINE_ITEMS_LOCK}:{tier.value}")
        row = await self._tiers.upsert(
            CreatePricingTierConfigDto(tier=tier.value, price_ngn_kobo=price_minor).model_dump(by_alias=False),
            ["price_ngn_kobo"],
            unique_index="uq_pricing_tier_config_tier",
        )
        for existing in await self._line_items.list_for_tier(tier.value):
            await self._line_items.soft_delete(existing.id)
        for order, item in enumerate(items):
            await self._line_items.create_return_model(CreatePricingLineItemDto(
                tier=tier.value, label=item.label.strip(), amount_minor=item.amount_minor, sort_order=order,
            ))
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="pricing_tier_config", resource_id=row.id, actor_id=admin_id,
            details={"tier": tier.value, "price_ngn_kobo": price_minor, "line_items": len(items)},
        )
        return row

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _validate_pricing(price_minor: int, items: List[LineItemInputDto]) -> None:
        if price_minor < 0:
            raise ValidationException(message="The price cannot be negative.")
        if any(item.amount_minor < 0 for item in items):
            raise ValidationException(message="A line item cannot be negative.")
        if any(not item.label.strip() for item in items):
            raise ValidationException(message="Every line item needs a label.")
        # No amounts in the message: `naira` shows whole naira, so a few kobo out would read
        # as "₦70,000, not ₦70,000".
        if items and sum(item.amount_minor for item in items) != price_minor:
            raise ValidationException(message="The line items must add up to exactly the tier's price.")

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
