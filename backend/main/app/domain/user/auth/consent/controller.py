from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from kink import di
from libre_fastapi_jwt import AuthJWT
from starlette.requests import Request

from main.app.domain.user.auth.consent.models import (
    AcceptConsentsDto,
    ConsentDocumentDto,
    LegalDocumentDto,
    LegalDocumentListDto,
    MissingConsentsDto,
    UserConsentHistoryPageDto,
)
from main.app.domain.user.auth.consent.service import ConsentService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

consent_router = APIRouter(prefix="/consents", tags=["Consents"])
consent_service: ConsentService = di[ConsentService]


# ── Public legal documents (rendered on the marketing /legal/* pages) ───────
# Unauthenticated: legal pages are public and crawlable (PRD R1.6).

@consent_router.get("/documents", response_model=SuccessResponse[LegalDocumentListDto])
async def list_legal_documents():
    docs = await consent_service.list_legal_documents()
    return SuccessResponse[LegalDocumentListDto](data=LegalDocumentListDto(documents=docs))


@consent_router.get("/documents/{slug}", response_model=SuccessResponse[LegalDocumentDto])
async def get_legal_document(slug: str):
    doc = await consent_service.get_legal_document(slug)
    if not doc:
        raise ResourceNotFoundException(resource=f"legal document /legal/{slug}")
    return SuccessResponse[LegalDocumentDto](data=doc)


@consent_router.get("/missing", response_model=SuccessResponse[MissingConsentsDto])
async def missing_consents(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    docs = await consent_service.list_missing_required_consents(str(user_id))
    return SuccessResponse[MissingConsentsDto](data=MissingConsentsDto(
        documents=[ConsentDocumentDto(
            type=d.type,
            consent_version=d.consent_version,
            effective_at=d.effective_at,
            title=d.title,
            href=d.href,
        ) for d in docs],
    ))


@consent_router.post("/accept", response_model=SuccessResponse[bool])
async def accept_consents(
        req: AcceptConsentsDto,  # forward ref
        request: Request,
        authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    for c in req.consents:
        await consent_service.record_user_consent(
            user_id=user_id,
            document_type=c.document_type,
            consent_version=c.consent_version,
            ip_address=ClientUtils.get_client_ip(request),
        )
    return SuccessResponse[bool](data=True)


# ── S57 — R19.4 consent history ─────────────────────────────────────────────

@consent_router.get("/history", response_model=SuccessResponse[UserConsentHistoryPageDto])
async def list_consent_history(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    result = await consent_service.list_for_user(user_id=user_id, page=page, page_size=page_size)
    return SuccessResponse.ok(result)


@consent_router.get("/history/download")
async def download_consent_history(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    csv_bytes = await consent_service.export_for_user_csv(user_id=user_id)

    def _stream():
        yield csv_bytes

    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"consent-history.csv\""},
    )
