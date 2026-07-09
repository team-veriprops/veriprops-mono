"""Public configuration endpoint."""
from fastapi import APIRouter

from main.app.config.settings import settings
from main.app.domain.config.models import PublicConfigDto
from main.app.domain.config.nigeria_locations import NigeriaLocationsDto, nigeria_locations
from main.appodus_utils.db.models import SuccessResponse

config_router = APIRouter(prefix="/config", tags=["Config"])


@config_router.get("/public", response_model=SuccessResponse[PublicConfigDto])
async def public_config():
    return SuccessResponse[PublicConfigDto](data=PublicConfigDto(
        phone_verification_enabled=settings.PHONE_VERIFICATION_ENABLED,
        legal_opinion_enabled=settings.LEGAL_OPINION_ENABLED,
    ))


@config_router.get("/nigeria-locations", response_model=SuccessResponse[NigeriaLocationsDto])
async def nigeria_locations_endpoint():
    """Canonical Nigerian states (§16.1, D33) — the coverage picker/map source of truth."""
    return SuccessResponse[NigeriaLocationsDto](data=nigeria_locations())
