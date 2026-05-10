"""Verification HTTP routes — PRD Phase 5+.

URL shape: `/verifications/...`
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.verification.models import (
    ConsentsAcceptedDto,
    DocumentUploadResponseDto,
    PricingSnapshotDto,
    PropertyDocumentType,
    TierSelectionDto,
    VerificationDto,
    VerificationTier,
    WizardStepDto,
)
from main.app.domain.verification.parser.models import ParseListingRequest, ParseResultDto
from main.app.domain.verification.parser.service import ListingParserService
from main.app.domain.verification.pricing.service import PricingService
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse

logger: Logger = di["logger"]

verification_service: VerificationService = di[VerificationService]
pricing_service: PricingService = di[PricingService]
listing_parser_service: ListingParserService = di[ListingParserService]

verification_router = APIRouter(prefix="/verifications", tags=["Verifications"])


@verification_router.get("/me", response_model=SuccessResponse[VerificationDto])
async def get_my_active_draft(authorize: AuthJWT = Depends()):
    """Return the active DRAFT for the caller, creating one if none exists."""
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await verification_service.create_or_resume_draft(user_id)
    return SuccessResponse[VerificationDto](data=dto)


@verification_router.get("/{verification_id}", response_model=SuccessResponse[VerificationDto])
async def get_verification(verification_id: str, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await verification_service.get(verification_id, user_id)
    return SuccessResponse[VerificationDto](data=dto)


@verification_router.post("/{verification_id}/draft", response_model=SuccessResponse[VerificationDto])
async def update_draft(
    verification_id: str, req: WizardStepDto, authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await verification_service.update_draft_step(user_id, verification_id, req)
    return SuccessResponse[VerificationDto](data=dto)


@verification_router.post(
    "/{verification_id}/tier",
    response_model=SuccessResponse[VerificationDto],
)
async def select_tier(
    verification_id: str, req: TierSelectionDto, authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await verification_service.select_tier(user_id, verification_id, req.tier, req.currency)
    return SuccessResponse[VerificationDto](data=dto)


@verification_router.post(
    "/{verification_id}/submit",
    response_model=SuccessResponse[VerificationDto],
)
async def submit_verification(
    verification_id: str,
    req: ConsentsAcceptedDto,
    request: Request,
    authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await verification_service.submit(
        user_id,
        verification_id,
        req.consents,
        ip_address=ClientUtils.get_client_ip(request),
        device_fingerprint=request.headers.get("X-Device-Fingerprint"),
    )
    return SuccessResponse[VerificationDto](data=dto)


@verification_router.get("/me/list", response_model=Page)
async def list_my_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    return await verification_service.list_for_customer(user_id, page=page, page_size=page_size)


@verification_router.post(
    "/{verification_id}/documents",
    response_model=SuccessResponse[DocumentUploadResponseDto],
)
async def upload_property_document(
    verification_id: str,
    file: UploadFile,
    document_type: PropertyDocumentType = Form(PropertyDocumentType.OTHER),
    authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    file_bytes = await file.read()
    dto = await verification_service.upload_document(
        user_id, verification_id, file_bytes, file.filename or "upload", document_type.value,
    )
    return SuccessResponse[DocumentUploadResponseDto](data=dto)


# ── Listing-URL parser (R5.2) ─────────────────────────────────────


@verification_router.post(
    "/{verification_id}/parse-listing",
    response_model=SuccessResponse[ParseResultDto],
)
async def parse_listing_url(
    verification_id: str, req: ParseListingRequest, authorize: AuthJWT = Depends(),
):
    """Fetch and parse a property listing URL, returning pre-filled fields.

    Always returns HTTP 200 — failures are surfaced as ParseResultDto(success=False)
    so the wizard can gracefully fall back to manual entry.
    """
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    # Ownership + draft guard via service (raises on ownership mismatch or non-draft).
    from main.app.domain.verification.models import VerificationStatus
    from main.appodus_utils.exception.exceptions import ValidationException
    dto = await verification_service.get(verification_id, user_id)
    if dto.status != VerificationStatus.DRAFT:
        raise ValidationException(message="Verification is no longer a draft")
    result = await listing_parser_service.parse(req.url)
    return SuccessResponse[ParseResultDto](data=result)


# ── Pricing endpoints (public quote, no auth) ───────────────────


@verification_router.get(
    "/pricing/quote",
    response_model=SuccessResponse[PricingSnapshotDto],
)
async def quote_pricing(
    tier: VerificationTier = Query(VerificationTier.STANDARD),
    currency: str = Query("NGN"),
):
    return SuccessResponse[PricingSnapshotDto](data=pricing_service.quote(tier, currency))
