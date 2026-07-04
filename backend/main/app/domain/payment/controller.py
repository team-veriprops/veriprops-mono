"""Payment controller (PRD §4.4, §5.4). URL shape: /payments/..."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Header
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.payment.models import (
    InitiatePaymentDto,
    Payment,
    PaymentDto,
    PaymentWebhookDto,
)
from main.app.domain.payment.service import PaymentService
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

from main.app.domain.payment.chargeback.controller import chargeback_router

payment_router = APIRouter(prefix="/payments", tags=["Payments"])
payment_service: PaymentService = di[PaymentService]
# Chargeback ingestion is a child of the payment domain (§6a.1).
payment_router.include_router(chargeback_router)


def _to_dto(p: Payment) -> PaymentDto:
    return PaymentDto(
        id=p.id,
        verification_id=p.verification_id,
        tx_ref=p.tx_ref,
        method=p.method,
        status=p.status,
        amount_minor=p.amount_minor,
        currency=TransactionCurrency(p.currency),
        charge_currency=TransactionCurrency(p.charge_currency) if p.charge_currency else None,
        charge_amount_minor=p.charge_amount_minor,
        checkout_url=p.checkout_url,
        date_created=p.date_created,
    )


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
    return SuccessResponse[PaymentDto](data=_to_dto(payment))


@payment_router.post("/stub/confirm", response_model=SuccessResponse[dict])
async def stub_confirm_payment(
    tx_ref: str = Body(..., embed=True),
    succeeded: bool = Body(default=True, embed=True),
    authorize: AuthJWT = Depends(),
):
    """Deterministic completion for local/test/dev — routes through the idempotent
    webhook handler. Non-prod only (PAYMENT_STUB_MODE); production uses real gateway
    webhooks. The event id is derived from tx_ref so a repeat confirm is a no-op."""
    if not settings.PAYMENT_STUB_MODE:
        raise ResourceNotFoundException(resource="stub payment confirm")
    await authorize.jwt_required()
    processed = await payment_service.handle_webhook(
        PaymentWebhookDto(event_id=f"stub-{tx_ref}", tx_ref=tx_ref, succeeded=succeeded)
    )
    return SuccessResponse[dict](data={"processed": processed})
