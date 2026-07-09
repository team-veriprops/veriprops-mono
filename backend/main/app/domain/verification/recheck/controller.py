"""Re-check controller (PRD §14.1).

Customer endpoints under /verifications/{id}/rechecks (JWT-owned) + admin decision endpoints
under /admin/rechecks (RBAC MANAGE_VERIFICATIONS). Frontend service:
frontend/src/components/portal/libs/recheck-service (+ admin recheck service).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.payment.service import PaymentService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.recheck.models import (
    DecideRecheckDto,
    RecheckDto,
    RecheckRequest,
    RecheckStatus,
    RequestRecheckDto,
)
from main.app.domain.verification.recheck.service import RecheckService
from main.appodus_utils.db.models import Page, SuccessResponse

recheck_router = APIRouter(prefix="/verifications", tags=["Verification Re-check"])
admin_recheck_router = APIRouter(prefix="/admin/rechecks", tags=["Admin: Re-checks"])
recheck_service: RecheckService = di[RecheckService]
payment_service: PaymentService = di[PaymentService]


async def _to_dto(r: RecheckRequest) -> RecheckDto:
    checkout_url: Optional[str] = None
    if r.status == RecheckStatus.APPROVED.value and r.payment_id:
        payment = await payment_service.get_payment(r.payment_id)
        checkout_url = payment.checkout_url if payment else None
    return RecheckDto(
        id=r.id, verification_id=r.verification_id, reason=r.reason, documents=r.documents,
        scope_roles=r.scope_roles, status=RecheckStatus(r.status), price_minor=r.price_minor,
        payment_id=r.payment_id, checkout_url=checkout_url, decision_note=r.decision_note,
        date_created=r.date_created,
    )


@recheck_router.post("/{verification_id}/rechecks", response_model=SuccessResponse[RecheckDto])
async def request_recheck(
    verification_id: str, req: RequestRecheckDto, authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    recheck = await recheck_service.request(verification_id, customer_id, req)
    return SuccessResponse[RecheckDto](data=await _to_dto(recheck))


@recheck_router.get("/{verification_id}/rechecks", response_model=SuccessResponse[List[RecheckDto]])
async def list_rechecks(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    rows = await recheck_service.list_for_verification(verification_id, customer_id)
    return SuccessResponse[List[RecheckDto]](data=[await _to_dto(r) for r in rows])


@admin_recheck_router.get("", response_model=SuccessResponse[Page[RecheckDto]])
async def list_pending(
    page: int = 0, page_size: int = 10,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[Page[RecheckDto]](data=await recheck_service.page_pending(page, page_size))


@admin_recheck_router.post("/{recheck_id}/decide", response_model=SuccessResponse[RecheckDto])
async def decide(
    recheck_id: str, req: DecideRecheckDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    recheck = await recheck_service.admin_decide(recheck_id, req, admin_id)
    return SuccessResponse[RecheckDto](data=await _to_dto(recheck))
