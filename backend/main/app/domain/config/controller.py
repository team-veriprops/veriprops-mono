"""Public configuration endpoint (unauthenticated)."""
from fastapi import APIRouter

from main.app.config.settings import settings
from main.app.domain.config.models import PublicConfigDto
from main.appodus_utils.db.models import SuccessResponse

config_router = APIRouter(prefix="/config", tags=["Config"])


@config_router.get("/public", response_model=SuccessResponse[PublicConfigDto])
async def public_config():
    """Runtime flags the frontend needs. Source of truth lives in backend settings."""
    return SuccessResponse[PublicConfigDto](data=PublicConfigDto(
        phone_verification_enabled=settings.PHONE_VERIFICATION_ENABLED,
    ))
