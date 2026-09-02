"""WhatsApp consent endpoints (PRD §7.4.6, WA-27).

URL shape: /channel/whatsapp/consent/... — session-authenticated. Frontend service:
frontend/src/components/account/libs/useWhatsAppConsentQueries.

One pair of endpoints serves both authenticated capture points: the payment step, where
§7.4.6 says the controls are first shown, and account settings, where they are revocable.
The third capture point — the `/wa/pay/<token>` landing — has no session and writes
through the grant-scoped route on the handoff router instead (D76).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.channel.whatsapp.consent.models import (
    SetWhatsAppConsentDto,
    WhatsAppConsentDto,
    WhatsAppConsentSource,
)
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.appodus_utils.db.models import SuccessResponse

whatsapp_consent_router = APIRouter(
    prefix="/channel/whatsapp/consent", tags=["WhatsApp Consent"]
)
consent_service: WhatsAppConsentService = di[WhatsAppConsentService]


@whatsapp_consent_router.get("/me", response_model=SuccessResponse[WhatsAppConsentDto])
async def get_my_consents(authorize: AuthJWT = Depends()):
    """This account's two §7.4.6 opt-ins. Absent means both off — never inherited."""
    await authorize.jwt_required()
    consents = await consent_service.describe(str(authorize.get_jwt_subject()))
    return SuccessResponse[WhatsAppConsentDto](data=consents)


@whatsapp_consent_router.put("/me", response_model=SuccessResponse[WhatsAppConsentDto])
async def set_my_consents(
    req: SetWhatsAppConsentDto,
    source: WhatsAppConsentSource = WhatsAppConsentSource.ACCOUNT_SETTINGS,
    authorize: AuthJWT = Depends(),
):
    """Record both controls as the customer left them.

    `source` is a query parameter rather than a body field so a client cannot claim a
    capture point it is not: the two authenticated surfaces are the pay screen and account
    settings, and the chat keywords write through the bot, never through here.
    """
    await authorize.jwt_required()
    if source in (WhatsAppConsentSource.STOP_KEYWORD, WhatsAppConsentSource.START_KEYWORD):
        # Those two are provenance the bot records about words the customer typed in
        # WhatsApp. A browser asserting them would corrupt the §7.8 export.
        source = WhatsAppConsentSource.ACCOUNT_SETTINGS
    consents = await consent_service.set_consents(
        str(authorize.get_jwt_subject()), req.utility, req.marketing, source
    )
    return SuccessResponse[WhatsAppConsentDto](data=consents)
