"""WhatsApp account-linking endpoints (PRD §7.4.4).

URL shape: /channel/whatsapp/link/... — all session-authenticated. Frontend service:
frontend/src/components/account/libs/useWhatsAppLinkQueries.

Two directions, both ending in the same confirm step:

* **Web→WhatsApp** (`/me/...`): the customer names the number from account settings.
* **WhatsApp→web** (`/from-token/...`): the *bot* named the number, and it travels in a
  signed single-use token. The browser never gets to nominate a number in this direction —
  that is the whole point of the token — so a logged-in attacker cannot have a code posted
  to a number the bot never messaged.

Linking is an identity operation, so the start endpoints are rate-limited alongside the
other OTP-issuing routes: the OTP service caps resends per number, and this caps the
attempt rate per client.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.channel.whatsapp.link.models import (
    ConfirmWhatsAppLinkDto,
    ConfirmWhatsAppLinkFromTokenDto,
    StartWhatsAppLinkDto,
    StartWhatsAppLinkFromTokenDto,
    WhatsAppLinkChallengeDto,
    WhatsAppLinkDto,
    WhatsAppLinkStatus,
)
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import SuccessResponse

whatsapp_link_router = APIRouter(prefix="/channel/whatsapp/link", tags=["WhatsApp Linking"])
link_service: WhatsAppLinkService = di[WhatsAppLinkService]

_start_rate_limit = RateLimiter(scope="wa_link_start", limit=10, window_seconds=300)


def _to_dto(link) -> WhatsAppLinkDto:
    """What the settings page renders — never the `wa_id` or the row's own id."""
    if link is None:
        return WhatsAppLinkDto(status=WhatsAppLinkStatus.REVOKED)
    return WhatsAppLinkDto(
        phone_e164=link.phone_e164,
        status=WhatsAppLinkStatus(link.status),
        linked_at=link.linked_at,
    )


@whatsapp_link_router.get("/me", response_model=SuccessResponse[WhatsAppLinkDto])
async def get_my_link(authorize: AuthJWT = Depends()):
    """This account's WhatsApp link, if it has one."""
    await authorize.jwt_required()
    link = await link_service.get_for_user(str(authorize.get_jwt_subject()))
    return SuccessResponse[WhatsAppLinkDto](data=_to_dto(link))


@whatsapp_link_router.post("/me/start", response_model=SuccessResponse[WhatsAppLinkChallengeDto])
async def start_my_link(
    req: StartWhatsAppLinkDto,
    authorize: AuthJWT = Depends(),
    _: None = Depends(_start_rate_limit),
):
    """Send a linking code to the number over WhatsApp (§7.4.4, D46)."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    challenge = await link_service.start_link(user_id, req.phone_e164)
    return SuccessResponse[WhatsAppLinkChallengeDto](data=challenge)


@whatsapp_link_router.post("/me/confirm", response_model=SuccessResponse[WhatsAppLinkDto])
async def confirm_my_link(req: ConfirmWhatsAppLinkDto, authorize: AuthJWT = Depends()):
    """Prove control of the number and establish the link."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    link = await link_service.confirm_link(user_id, req.phone_e164, req.code)
    return SuccessResponse[WhatsAppLinkDto](data=_to_dto(link))


@whatsapp_link_router.delete("/me", response_model=SuccessResponse[dict])
async def unlink_my_number(authorize: AuthJWT = Depends()):
    """Drop the link. The old WhatsApp thread goes cold immediately (§7.4.4)."""
    await authorize.jwt_required()
    await link_service.unlink(str(authorize.get_jwt_subject()))
    return SuccessResponse[dict](data={"unlinked": True})


@whatsapp_link_router.post(
    "/from-token/start", response_model=SuccessResponse[WhatsAppLinkChallengeDto]
)
async def start_link_from_token(
    req: StartWhatsAppLinkFromTokenDto,
    authorize: AuthJWT = Depends(),
    _: None = Depends(_start_rate_limit),
):
    """Begin the WhatsApp→web direction: the number comes from the bot's signed link."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    challenge = await link_service.start_link_from_token(user_id, req.token)
    return SuccessResponse[WhatsAppLinkChallengeDto](data=challenge)


@whatsapp_link_router.post(
    "/from-token/confirm", response_model=SuccessResponse[WhatsAppLinkDto]
)
async def confirm_link_from_token(
    req: ConfirmWhatsAppLinkFromTokenDto, authorize: AuthJWT = Depends()
):
    """Complete the WhatsApp→web direction, spending the bot's link exactly once."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    link = await link_service.confirm_link_from_token(user_id, req.token, req.code)
    return SuccessResponse[WhatsAppLinkDto](data=_to_dto(link))
