"""Admin pricing controller — S54."""
from __future__ import annotations

from typing import List

from fastapi import Depends
from kink import di

from main.app.domain.verification.pricing.models import (
    PricingTierConfigDto,
    PricingUpgradeDeltaDto,
    UpdatePricingTierConfigDto,
    UpsertPricingTierDto,
    UpsertUpgradeDeltaDto,
)
from main.app.domain.verification.pricing.service import PricingService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

pricing_admin_router = AppRouter(prefix="/admin/pricing", tags=["Pricing"])

_auth = AuthJWTBearer(required_permissions=["CONFIGURE_PRICING"])


@pricing_admin_router.get("/tiers", response_model=SuccessResponse[List[PricingTierConfigDto]])
async def list_tiers(_: JWTClaims = Depends(_auth)):
    svc: PricingService = di[PricingService]
    tiers = await svc.list_tier_configs()
    return SuccessResponse.ok(tiers)


@pricing_admin_router.post("/tiers", response_model=SuccessResponse[PricingTierConfigDto])
async def upsert_tier(dto: UpsertPricingTierDto, claims: JWTClaims = Depends(_auth)):
    svc: PricingService = di[PricingService]
    result = await svc.upsert_tier(dto, claims.sub)
    return SuccessResponse.ok(result)


@pricing_admin_router.put("/tiers/{tier}", response_model=SuccessResponse[PricingTierConfigDto])
async def update_tier(tier: str, dto: UpdatePricingTierConfigDto, claims: JWTClaims = Depends(_auth)):
    svc: PricingService = di[PricingService]
    result = await svc.update_tier(tier, dto, claims.sub)
    return SuccessResponse.ok(result)


@pricing_admin_router.get("/upgrade-deltas", response_model=SuccessResponse[List[PricingUpgradeDeltaDto]])
async def list_upgrade_deltas(_: JWTClaims = Depends(_auth)):
    svc: PricingService = di[PricingService]
    deltas = await svc.list_upgrade_deltas()
    return SuccessResponse.ok(deltas)


@pricing_admin_router.put("/upgrade-deltas", response_model=SuccessResponse[PricingUpgradeDeltaDto])
async def upsert_upgrade_delta(dto: UpsertUpgradeDeltaDto, claims: JWTClaims = Depends(_auth)):
    svc: PricingService = di[PricingService]
    result = await svc.upsert_upgrade_delta(dto, claims.sub)
    return SuccessResponse.ok(result)
