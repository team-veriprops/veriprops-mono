"""Public configuration endpoint."""
from fastapi import APIRouter
from kink import di

from main.app.config.settings import settings
from main.app.core.state.status import VerificationTier
from main.app.domain.config.models import PublicConfigDto, PublicPricingTierDto
from main.app.domain.config.nigeria_locations import NigeriaLocationsDto, nigeria_locations
from main.app.domain.verification.pricing_config.service import PricingConfigService
from main.appodus_utils.db.models import SuccessResponse

config_router = APIRouter(prefix="/config", tags=["Config"])
pricing_config_service: PricingConfigService = di[PricingConfigService]


@config_router.get("/public", response_model=SuccessResponse[PublicConfigDto])
async def public_config():
    pricing_tiers = [
        PublicPricingTierDto(tier=tier, price_ngn_minor=await pricing_config_service.tier_price_kobo(tier))
        for tier in VerificationTier
    ]
    return SuccessResponse[PublicConfigDto](data=PublicConfigDto(
        phone_verification_enabled=settings.PHONE_VERIFICATION_ENABLED,
        legal_opinion_enabled=settings.LEGAL_OPINION_ENABLED,
        chat_message_max_length=settings.CHAT_MESSAGE_MAX_LENGTH,
        pricing_tiers=pricing_tiers,
    ))


@config_router.get("/nigeria-locations", response_model=SuccessResponse[NigeriaLocationsDto])
async def nigeria_locations_endpoint():
    """Canonical Nigerian states (§16.1, D33) — the coverage picker/map source of truth."""
    return SuccessResponse[NigeriaLocationsDto](data=nigeria_locations())
