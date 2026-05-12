"""Tier upgrade endpoints — S45."""
from __future__ import annotations

from fastapi import Depends

from main.app.domain.verification.tier_upgrade.models import (
    SubmitTierUpgradeDto,
    TierUpgradeDto,
    TierUpgradePreviewDto,
)
from main.app.domain.verification.tier_upgrade.service import TierUpgradeService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

tier_upgrade_router = AppRouter(tags=["Tier Upgrade"])

_auth = AuthJWTBearer()


@tier_upgrade_router.get(
    "/portal/verifications/{vid}/upgrade/preview",
    response_model=SuccessResponse[TierUpgradePreviewDto],
)
async def preview_upgrade(vid: str, claims: JWTClaims = Depends(_auth)):
    svc: TierUpgradeService = di[TierUpgradeService]
    preview = await svc.preview(vid)
    return SuccessResponse.ok(preview)


@tier_upgrade_router.post(
    "/portal/verifications/{vid}/upgrade",
    response_model=SuccessResponse[TierUpgradeDto],
)
async def submit_upgrade(vid: str, dto: SubmitTierUpgradeDto, claims: JWTClaims = Depends(_auth)):
    svc: TierUpgradeService = di[TierUpgradeService]
    result = await svc.submit(vid, claims.sub, dto)
    return SuccessResponse.ok(result)
