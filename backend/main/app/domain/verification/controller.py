"""Verification submission controller (PRD §5). URL shape: /verifications/..."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.state.status import VerificationTier
from main.app.domain.verification.models import (
    PriceQuoteDto,
    SaveVerificationDraftDto,
    SubmitVerificationDto,
    Verification,
    VerificationDraftDto,
    VerificationDto,
)
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.geocoding.factory import GeocoderFactory
from main.appodus_utils.integrations.geocoding.models import GeoLocation, GeoSuggestion

verification_router = APIRouter(prefix="/verifications", tags=["Verifications"])
verification_service: VerificationService = di[VerificationService]
geocoder_factory: GeocoderFactory = di[GeocoderFactory]


def _to_dto(v: Verification) -> VerificationDto:
    return VerificationDto(
        id=v.id,
        vid=v.vid,
        status=v.status,
        tier=VerificationTier(v.tier) if v.tier else None,
        property_id=v.property_id,
        price_locked_minor=v.price_locked_minor,
        currency=TransactionCurrency(v.currency),
        charge_currency=TransactionCurrency(v.charge_currency) if v.charge_currency else None,
        charge_amount_minor=v.charge_amount_minor,
        fx_rate_at_quote=v.fx_rate_at_quote,
        price_lock_expires_at=v.price_lock_expires_at,
        paid_at=v.paid_at,
        sla_due_date=v.sla_due_date,
        draft_step=v.draft_step or 0,
    )


def _to_draft_dto(v: Verification) -> VerificationDraftDto:
    return VerificationDraftDto(
        id=v.id,
        vid=v.vid,
        status=v.status,
        step=v.draft_step or 0,
        payload=json.loads(v.draft_payload) if v.draft_payload else {},
    )


@verification_router.post("/draft", response_model=SuccessResponse[VerificationDraftDto])
async def create_draft(
    authorize: AuthJWT = Depends(),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    v = await verification_service.create_draft(customer_id, idempotency_key=idempotency_key)
    return SuccessResponse[VerificationDraftDto](data=_to_draft_dto(v))


@verification_router.put("/{verification_id}/draft", response_model=SuccessResponse[VerificationDraftDto])
async def save_draft(verification_id: str, req: SaveVerificationDraftDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    v = await verification_service.save_draft(verification_id, customer_id, req)
    return SuccessResponse[VerificationDraftDto](data=_to_draft_dto(v))


@verification_router.get("/geo/autocomplete", response_model=SuccessResponse[list[GeoSuggestion]])
async def geo_autocomplete(q: str = Query(...), authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    suggestions = await geocoder_factory.get_active_provider().autocomplete(q, country="NG")
    return SuccessResponse[list[GeoSuggestion]](data=suggestions)


@verification_router.get("/geo/place/{place_id}", response_model=SuccessResponse[Optional[GeoLocation]])
async def geo_place(place_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    loc = await geocoder_factory.get_active_provider().geocode(place_id)
    return SuccessResponse[Optional[GeoLocation]](data=loc)


@verification_router.get("/quote", response_model=SuccessResponse[PriceQuoteDto])
async def get_quote(
    tier: VerificationTier = Query(...),
    currency: TransactionCurrency = Query(default=TransactionCurrency.NGN),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    return SuccessResponse[PriceQuoteDto](data=verification_service.quote(tier, currency))


@verification_router.get("/{verification_id}", response_model=SuccessResponse[VerificationDto])
async def get_verification(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    v = await verification_service.get_owned(verification_id, customer_id)
    return SuccessResponse[VerificationDto](data=_to_dto(v))


@verification_router.get("/{verification_id}/draft", response_model=SuccessResponse[VerificationDraftDto])
async def get_draft(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    v = await verification_service.get_owned(verification_id, customer_id)
    return SuccessResponse[VerificationDraftDto](data=_to_draft_dto(v))


@verification_router.post("/{verification_id}/submit", response_model=SuccessResponse[VerificationDto])
async def submit_verification(
    verification_id: str, req: SubmitVerificationDto, request: Request, authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    v = await verification_service.submit(
        verification_id, customer_id, req, ip_address=ClientUtils.get_client_ip(request)
    )
    return SuccessResponse[VerificationDto](data=_to_dto(v))
