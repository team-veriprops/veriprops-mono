"""Pricing service — quote computation + 24-hr price lock.

Quotes are derived from the static `config.TIER_MATRIX` and an FX cache.
On "continue to payment" the verification stores the locked snapshot in JSON.
"""
from __future__ import annotations

import time
from typing import Dict, Tuple

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
from main.appodus_utils.exception.exceptions import ValidationException


# Module-level FX cache: { currency: (rate, fetched_at_epoch) }.
# Process-local — fine for a single service; replace with Redis when scale demands.
_FX_CACHE: Dict[str, Tuple[float, float]] = {}


@inject
class PricingService:
    """Pure-compute service. No DB writes — the verification service is in
    charge of persisting the pricing snapshot."""

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
