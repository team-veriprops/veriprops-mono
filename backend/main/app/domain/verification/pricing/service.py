"""Pricing service — quote computation + 24-hr price lock.

Quotes are derived from the static `config.TIER_MATRIX` and an FX cache.
On "continue to payment" the verification stores the locked snapshot in JSON.

Phase 18 (S54): DB-backed pricing methods added alongside the static quote()
to avoid breaking existing wizard flows.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from kink import inject

from main.app.config.settings import settings
from main.app.domain.verification.models import (
    PricingLineItemDto,
    PricingSnapshotDto,
    VerificationTier,
)
from main.app.domain.verification.pricing.config import (
    STUB_FX_RATES,
    SUPPORTED_CURRENCIES,
    line_items_for_tier,
)
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException


# Module-level FX cache: { currency: (rate, fetched_at_epoch) }.
# Process-local — fine for a single service; replace with Redis when scale demands.
_FX_CACHE: Dict[str, Tuple[float, float]] = {}


@inject
@decorate_all_methods(transactional(), exclude=["__init__", "quote", "lock", "_get_fx_rate"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PricingService:
    """Pure-compute service. No DB writes — the verification service is in
    charge of persisting the pricing snapshot."""

    def __init__(self):
        # Repos injected lazily to avoid circular deps with existing non-DI usage
        self._tier_repo: Optional["PricingTierConfigRepo"] = None
        self._line_item_repo: Optional["PricingLineItemRepo"] = None
        self._delta_repo: Optional["PricingUpgradeDeltaRepo"] = None

    def _get_repos(self):
        if self._tier_repo is None:
            from kink import di
            from main.app.domain.verification.pricing.repo import (
                PricingLineItemRepo,
                PricingTierConfigRepo,
                PricingUpgradeDeltaRepo,
            )
            self._tier_repo = di[PricingTierConfigRepo]
            self._line_item_repo = di[PricingLineItemRepo]
            self._delta_repo = di[PricingUpgradeDeltaRepo]

    def quote(self, tier: VerificationTier, currency: str = "NGN") -> PricingSnapshotDto:
        currency = (currency or "NGN").upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValidationException(message=f"Unsupported currency: {currency}")

        ngn_items: list[PricingLineItemDto] = line_items_for_tier(tier)
        rate, fetched_at, stale = self._get_fx_rate(currency)

        # Convert each item to the requested currency, rounding minor units to int.
        if currency == "NGN" or rate == 1.0:
            converted = ngn_items
            base_amount = sum(it.amount_minor for it in converted)
        else:
            converted = [
                PricingLineItemDto(
                    label=it.label,
                    amount_minor=int(round(it.amount_minor * rate)),
                    description=it.description,
                )
                for it in ngn_items
            ]
            base_amount = sum(it.amount_minor for it in converted)

        return PricingSnapshotDto(
            tier=tier,
            currency=currency,
            base_amount_minor=base_amount,
            line_items=converted,
            total_amount_minor=base_amount,
            fx_rate=rate if currency != "NGN" else None,
            fx_source_currency="NGN",
            fx_fetched_at=Utils.datetime_now() if currency != "NGN" else None,
            fx_stale=stale,
        )

    def lock(self, snapshot: PricingSnapshotDto) -> PricingSnapshotDto:
        ttl_hours = settings.PRICE_LOCK_TTL_HOURS or 24
        locked_at = Utils.datetime_now()
        locked_until = Utils.datetime_now_plus(hours=ttl_hours)
        return snapshot.model_copy(update={
            "locked_at": locked_at,
            "locked_until": locked_until,
        })

    # ── Admin DB-backed methods (S54) ────────────────────────────

    async def list_tier_configs(self):
        from main.app.domain.verification.pricing.models import PricingTierConfigDto, PricingLineItemDto as PricingLIDto
        self._get_repos()
        configs = await self._tier_repo.list_all_active()
        result = []
        for cfg in configs:
            line_items = await self._line_item_repo.list_for_config(str(cfg.id))
            result.append(self._config_to_dto(cfg, line_items))
        return result

    async def upsert_tier(self, dto, admin_id: str):
        from main.app.domain.verification.pricing.models import (
            CreatePricingTierConfigDto,
            CreatePricingLineItemDto,
            UpdatePricingTierConfigDto,
        )
        self._get_repos()
        existing = await self._tier_repo.get_for_tier_currency(dto.tier, dto.currency)
        if existing is None:
            cfg = await self._tier_repo.create(CreatePricingTierConfigDto(
                tier=dto.tier,
                label=dto.label,
                currency=dto.currency,
                service_fee_minor=dto.service_fee_minor,
                updated_by=admin_id,
            ))
        else:
            await self._tier_repo.update(str(existing.id), UpdatePricingTierConfigDto(
                label=dto.label,
                service_fee_minor=dto.service_fee_minor,
                is_active=True,
                updated_by=admin_id,
            ))
            cfg = await self._tier_repo.get_model(str(existing.id))

        # Replace line items
        await self._line_item_repo.delete_for_config(str(cfg.id))
        for li in dto.line_items:
            await self._line_item_repo.create(CreatePricingLineItemDto(
                tier_config_id=str(cfg.id),
                label=li.label,
                amount_minor=li.amount_minor,
                description=li.description,
                sort_order=li.sort_order,
            ))

        line_items = await self._line_item_repo.list_for_config(str(cfg.id))
        return self._config_to_dto(cfg, line_items)

    async def update_tier(self, tier: str, dto, admin_id: str):
        from main.app.domain.verification.pricing.models import UpdatePricingTierConfigDto
        self._get_repos()
        existing = await self._tier_repo.get_active_for_tier(tier)
        if existing is None:
            raise ResourceNotFoundException(resource="PricingTierConfig")
        update = UpdatePricingTierConfigDto(**{k: v for k, v in dto.model_dump().items() if v is not None})
        update.updated_by = admin_id
        await self._tier_repo.update(str(existing.id), update)
        cfg = await self._tier_repo.get_model(str(existing.id))
        line_items = await self._line_item_repo.list_for_config(str(cfg.id))
        return self._config_to_dto(cfg, line_items)

    async def list_upgrade_deltas(self):
        self._get_repos()
        rows = await self._delta_repo.list_all()
        return [self._delta_to_dto(r) for r in rows]

    async def upsert_upgrade_delta(self, dto, admin_id: str):
        from main.app.domain.verification.pricing.models import (
            CreatePricingUpgradeDeltaDto,
            UpdatePricingUpgradeDeltaDto,
        )
        self._get_repos()
        existing = await self._delta_repo.get_for_pair(dto.from_tier, dto.to_tier, dto.currency)
        if existing is None:
            row = await self._delta_repo.create(CreatePricingUpgradeDeltaDto(
                from_tier=dto.from_tier,
                to_tier=dto.to_tier,
                delta_minor=dto.delta_minor,
                currency=dto.currency,
                updated_by=admin_id,
            ))
        else:
            await self._delta_repo.update(str(existing.id), UpdatePricingUpgradeDeltaDto(
                delta_minor=dto.delta_minor,
                updated_by=admin_id,
            ))
            row = await self._delta_repo.get_model(str(existing.id))
        return self._delta_to_dto(row)

    @staticmethod
    def _config_to_dto(cfg, line_items):
        from main.app.domain.verification.pricing.models import PricingTierConfigDto, PricingLineItemDto as PricingLIDto
        return PricingTierConfigDto(
            id=str(cfg.id),
            tier=cfg.tier,
            label=cfg.label,
            currency=cfg.currency,
            service_fee_minor=cfg.service_fee_minor,
            is_active=cfg.is_active,
            line_items=[
                PricingLIDto(
                    id=str(li.id),
                    label=li.label,
                    amount_minor=li.amount_minor,
                    description=li.description,
                    sort_order=li.sort_order,
                )
                for li in line_items
            ],
            updated_by=cfg.updated_by,
            date_updated=cfg.date_updated,
        )

    @staticmethod
    def _delta_to_dto(row):
        from main.app.domain.verification.pricing.models import PricingUpgradeDeltaDto
        return PricingUpgradeDeltaDto(
            id=str(row.id),
            from_tier=row.from_tier,
            to_tier=row.to_tier,
            delta_minor=row.delta_minor,
            currency=row.currency,
            updated_by=row.updated_by,
            date_updated=row.date_updated,
        )

    @staticmethod
    def _get_fx_rate(currency: str) -> tuple[float, float, bool]:
        if currency == "NGN":
            return 1.0, time.time(), False
        cached = _FX_CACHE.get(currency)
        cache_seconds = settings.PRICING_FX_CACHE_SECONDS or 300
        stale_after = settings.PRICING_FX_STALE_AFTER_SECONDS or 1800
        now = time.time()
        if cached and (now - cached[1]) < cache_seconds:
            return cached[0], cached[1], False
        # Stub provider — replace with live API in Phase 18.
        rate = STUB_FX_RATES.get(currency, 1.0)
        _FX_CACHE[currency] = (rate, now)
        stale = (now - cached[1]) > stale_after if cached else False
        return rate, now, stale
