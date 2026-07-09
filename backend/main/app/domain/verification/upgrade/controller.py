"""Tier-upgrade controller (PRD §14.2).

Customer endpoints under /verifications/{id}/upgrades (JWT-owned). Frontend service:
frontend/src/components/portal/libs/upgrade-service.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.state.status import VerificationTier
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.upgrade.models import (
    RequestUpgradeDto,
    UpgradeDto,
    UpgradeRequest,
    UpgradeStatus,
)
from main.app.domain.verification.upgrade.service import UpgradeService
from main.appodus_utils.db.models import SuccessResponse

upgrade_router = APIRouter(prefix="/verifications", tags=["Verification Tier Upgrade"])
upgrade_service: UpgradeService = di[UpgradeService]
payment_service: PaymentService = di[PaymentService]


async def _to_dto(u: UpgradeRequest) -> UpgradeDto:
    checkout_url: Optional[str] = None
    if u.status == UpgradeStatus.PENDING.value and u.payment_id:
        payment = await payment_service.get_payment(u.payment_id)
        checkout_url = payment.checkout_url if payment else None
    return UpgradeDto(
        id=u.id, verification_id=u.verification_id, from_tier=VerificationTier(u.from_tier),
        to_tier=VerificationTier(u.to_tier), delta_minor=u.delta_minor,
        status=UpgradeStatus(u.status), payment_id=u.payment_id, checkout_url=checkout_url,
        date_created=u.date_created,
    )


@upgrade_router.post("/{verification_id}/upgrades", response_model=SuccessResponse[UpgradeDto])
async def request_upgrade(
    verification_id: str, req: RequestUpgradeDto, authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    upgrade = await upgrade_service.request(verification_id, customer_id, req)
    return SuccessResponse[UpgradeDto](data=await _to_dto(upgrade))


@upgrade_router.get("/{verification_id}/upgrades", response_model=SuccessResponse[List[UpgradeDto]])
async def list_upgrades(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    rows = await upgrade_service.list_for_verification(verification_id, customer_id)
    return SuccessResponse[List[UpgradeDto]](data=[await _to_dto(u) for u in rows])
