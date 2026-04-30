from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT
from starlette.requests import Request

from main.app.domain.user.auth.consent.models import MissingConsentsDto, ConsentDocumentDto, AcceptConsentsDto
from main.app.domain.user.auth.consent.service import ConsentService
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import SuccessResponse

consent_router = APIRouter(prefix="/consents", tags=["Consents"])
consent_service: ConsentService = di[ConsentService]


@consent_router.get("/missing", response_model=SuccessResponse[MissingConsentsDto])
async def missing_consents(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    docs = await consent_service.list_missing_required_consents(user_id)
    return SuccessResponse[MissingConsentsDto](data=MissingConsentsDto(
        documents=[ConsentDocumentDto(
            type=d.type,
            version=d.version,
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
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    for c in req.consents:
        await consent_service.record_user_consent(
            user_id=user_id,
            document_type=c.document_type,
            consent_version=c.consent_version,
            ip_address=ClientUtils.get_client_ip(request),
        )
    return SuccessResponse[bool](data=True)
