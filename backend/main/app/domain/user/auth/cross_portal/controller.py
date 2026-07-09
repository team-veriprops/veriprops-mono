from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.cross_portal.models import CrossPortalSummaryDto
from main.app.domain.user.auth.cross_portal.service import CrossPortalService
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.appodus_utils.db.models import SuccessResponse

cross_portal_router = APIRouter(prefix="/cross-portal", tags=["Cross-portal"])

cross_portal_service: CrossPortalService = di[CrossPortalService]
user_service: UserService = di[UserService]


@cross_portal_router.get("/summary", response_model=SuccessResponse[CrossPortalSummaryDto])
async def cross_portal_summary(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    user = await user_service.get_user_model(user_id)
    personas = [UserPersona(p) for p in (user.personas or [])]
    data = await cross_portal_service.summary(user_id, personas)
    return SuccessResponse[CrossPortalSummaryDto](data=data)
