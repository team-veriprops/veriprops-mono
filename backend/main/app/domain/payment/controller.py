"""Payment controller (PRD §4.4, §5.4). URL shape: /payments/..."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.payment.models import (
    AdminPaymentDto,
    InitiatePaymentDto,
    PaymentDto,
    PaymentStatus,
    PaymentWebhookDto,
    payment_to_dto,
)
from main.app.domain.payment.service import PaymentService
from main.appodus_utils import Object
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

from main.app.domain.payment.chargeback.controller import chargeback_router

payment_router = APIRouter(prefix="/payments", tags=["Payments"])
# Finance's view of payments: the refunds a gateway refused, and their retry.
admin_payment_router = APIRouter(prefix="/admin/payments", tags=["Admin: Payments"])
payment_service: PaymentService = di[PaymentService]
# Chargeback ingestion is a child of the payment domain (§6a.1).
payment_router.include_router(chargeback_router)


@payment_router.post("/initiate/{verification_id}", response_model=SuccessResponse[PaymentDto])
async def initiate_payment(
    verification_id: str,
    req: InitiatePaymentDto,
    authorize: AuthJWT = Depends(),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    payment = await payment_service.initiate(
        verification_id, customer_id, req.method, idempotency_key=idempotency_key
    )
    return SuccessResponse[PaymentDto](data=payment_to_dto(payment))


@payment_router.post("/reconcile/{verification_id}", response_model=SuccessResponse[Optional[PaymentDto]])
async def reconcile_payment(verification_id: str, authorize: AuthJWT = Depends()):
    """The pay page's check on return from a hosted checkout (or on reload): asks the gateway
    about the customer's open payments on this verification, and returns the latest one."""
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    payment = await payment_service.reconcile_for_verification(verification_id, customer_id)
    return SuccessResponse[Optional[PaymentDto]](data=payment_to_dto(payment) if payment else None)


class StubConfirmPaymentDto(Object):
    """Body for the deterministic stub confirmation.

    A DTO rather than embedded `Body` scalars: `Body(embed=True)` binds the raw Python
    parameter name, so `tx_ref` would only ever accept snake_case while every client
    sends camelCase through the shared alias generator.
    """

    tx_ref: str
    succeeded: bool = True


@payment_router.post("/stub/confirm", response_model=SuccessResponse[dict])
async def stub_confirm_payment(
    req: StubConfirmPaymentDto,
    authorize: AuthJWT = Depends(),
):
    """Deterministic completion for local/test/dev — routes through the idempotent
    webhook handler. Non-prod only (PAYMENT_STUB_MODE); production uses real gateway
    webhooks. The event id is derived from tx_ref so a repeat confirm is a no-op."""
    if not settings.PAYMENT_STUB_MODE:
        raise ResourceNotFoundException(resource="stub payment confirm")
    await authorize.jwt_required()
    processed = await payment_service.handle_webhook(
        PaymentWebhookDto(
            event_id=f"stub-{req.tx_ref}", tx_ref=req.tx_ref, succeeded=req.succeeded
        )
    )
    return SuccessResponse[dict](data={"processed": processed})


@admin_payment_router.get("", response_model=SuccessResponse[Page[AdminPaymentDto]])
async def list_payments(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    query: Optional[str] = Query(default=None, max_length=100),
    status: Optional[PaymentStatus] = Query(default=None),
    _admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    """Every charge, newest first: finance's view of one payment's own state (§18.1)."""
    return SuccessResponse[Page[AdminPaymentDto]](
        data=await payment_service.page_for_admin(page, page_size, query, status)
    )


@admin_payment_router.get("/refund-retries", response_model=SuccessResponse[Page[PaymentDto]])
async def list_refund_retries(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    """Settled payments on verifications that were refunded or failed: a gateway refused to
    return the money, and finance retries it here."""
    return SuccessResponse[Page[PaymentDto]](data=await payment_service.page_refunds_to_retry(page, page_size))


@admin_payment_router.post("/{payment_id}/refund", response_model=SuccessResponse[PaymentDto])
async def retry_refund(
    payment_id: str,
    admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    payment = await payment_service.retry_refund(payment_id, admin_id)
    return SuccessResponse[PaymentDto](data=payment_to_dto(payment))
