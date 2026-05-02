"""Payment HTTP routes — PRD Phase 5 (§5.4)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from fastapi import APIRouter, Depends, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.payment.models import (
    ConfirmWireDto,
    InitiatePaymentDto,
    InitiatePaymentResultDto,
    PaymentDto,
    WireProofDto,
)
from main.app.domain.payment.service import PaymentService
from main.app.domain.user.auth.utils.permissions import (
    Permission,
    require_permission,
)
from main.appodus_utils.db.models import SuccessResponse

logger: Logger = di["logger"]

payment_service: PaymentService = di[PaymentService]

payment_router = APIRouter(prefix="/payments", tags=["Payments"])


@payment_router.post(
    "/initiate",
    response_model=SuccessResponse[InitiatePaymentResultDto],
)
async def initiate_payment(req: InitiatePaymentDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    result = await payment_service.initiate(user_id, req)
    return SuccessResponse[InitiatePaymentResultDto](data=result)


@payment_router.get("/{payment_id}", response_model=SuccessResponse[PaymentDto])
async def get_payment(payment_id: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await payment_service.get(user_id, payment_id)
    return SuccessResponse[PaymentDto](data=dto)


@payment_router.post(
    "/{payment_id}/wire-proof",
    response_model=SuccessResponse[PaymentDto],
)
async def upload_wire_proof(
    payment_id: str, req: WireProofDto, authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await payment_service.upload_wire_proof(user_id, payment_id, req)
    return SuccessResponse[PaymentDto](data=dto)


@payment_router.post(
    "/admin/{payment_id}/confirm-wire",
    response_model=SuccessResponse[PaymentDto],
)
async def admin_confirm_wire(
    payment_id: str,
    req: ConfirmWireDto,
    admin_id: str = Depends(require_permission(Permission.CONFIRM_WIRE_PAYMENT)),
):
    dto = await payment_service.confirm_wire(payment_id, admin_id, req)
    return SuccessResponse[PaymentDto](data=dto)


# ── Webhook ────────────────────────────────────────────────────


# Webhook handler is mounted under /webhooks separately. Stub here lets us
# call the service from a future webhook implementation; the receiving glue
# would translate provider payload to (provider_ref, status, payload).
