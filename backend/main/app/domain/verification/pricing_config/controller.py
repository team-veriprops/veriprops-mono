"""Pricing config admin controller (PRD §18.1, D36).

URL shape: /admin/pricing — RBAC-gated (CONFIGURE_PRICING, the Finance role). Edits take
effect on the next quote (existing 24h price locks are honoured). Frontend service:
frontend/src/components/admin/pricing/libs/pricing-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing_config.models import (
    SetTierPricingDto,
    TierPricingViewDto,
)
from main.app.domain.verification.pricing_config.service import PricingConfigService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

admin_pricing_router = APIRouter(prefix="/admin/pricing", tags=["Admin: Pricing"])
pricing_service: PricingConfigService = di[PricingConfigService]


@admin_pricing_router.get("", response_model=SuccessResponse[TierPricingViewDto])
async def get_pricing(_admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING))):
    """Every tier's price + line items + upgrade deltas (§18.1)."""
    return SuccessResponse[TierPricingViewDto](data=await pricing_service.view())


@admin_pricing_router.put("/tiers/{tier}", response_model=SuccessResponse[TierPricingViewDto])
async def set_tier_pricing(
    tier: VerificationTier,
    req: SetTierPricingDto,
    admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING)),
):
    """A tier's price and its line items, saved together (§18.1)."""
    await pricing_service.set_tier_pricing(tier, req.price_ngn_minor, req.line_items, admin_id)
    return SuccessResponse[TierPricingViewDto](data=await pricing_service.view())
