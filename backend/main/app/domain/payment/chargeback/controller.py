"""Chargeback ingestion controller (PRD §6a.1).

The chargeback *flag* originates gateway-side. In production the provider's
signed webhook drives ``ChargebackService.handle_webhook``; for local/test/dev a
deterministic non-prod stub endpoint injects the same event so the sub-process is
exercisable end-to-end (mirrors the payment ``/stub/confirm`` philosophy). Admin
rebuttal/resolve live on the admin verification router (§6a.2).

Mounted under the payment router (child of the payment parent domain).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.payment.chargeback.models import ChargebackWebhookDto
from main.app.domain.payment.chargeback.service import ChargebackService
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

# Mounted under the payment router (prefix "/payments"), yielding /payments/chargebacks/...
chargeback_router = APIRouter(prefix="/chargebacks", tags=["Payments: Chargebacks"])
chargeback_service: ChargebackService = di[ChargebackService]


@chargeback_router.post("/stub/flag", response_model=SuccessResponse[dict])
async def stub_flag_chargeback(
    req: ChargebackWebhookDto,
    authorize: AuthJWT = Depends(),
):
    """Deterministic chargeback-flag injection for local/test/dev — routes through the
    idempotent ``handle_webhook`` (§6a.2). Non-prod only (PAYMENT_STUB_MODE); production
    ingests real signed gateway chargeback webhooks. Idempotent on the event id."""
    if not settings.PAYMENT_STUB_MODE:
        raise ResourceNotFoundException(resource="stub chargeback flag")
    await authorize.jwt_required()
    chargeback = await chargeback_service.handle_webhook(req)
    return SuccessResponse[dict](data={"chargeback_id": chargeback.id if chargeback else None})
