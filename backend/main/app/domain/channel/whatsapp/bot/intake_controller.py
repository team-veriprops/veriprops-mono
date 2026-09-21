"""Chat-intake handoff endpoint (PRD §5.1, §26.5, D69/D71).

URL shape: /wa/intake — **authenticated**, unlike the other `/wa/*` landings. That is the
whole design: the chat could not establish who the customer is, so the landing does, and
the token only says which conversation's answers to pick up. Frontend: `/wa/intake/[token]`
(inside `PROTECTED_PREFIXES`, like `/wa/link/[token]`).

The token names a phone; the session names an account. Neither alone is enough — a
forwarded link opened by a signed-in stranger spends a nonce and seeds *their* draft with
answers they would then have to confirm on a real form, and the number it came from is
recorded in the redemption ledger either way.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.channel.whatsapp.analytics.models import WhatsAppChannelEventType
from main.app.domain.channel.whatsapp.analytics.recorder import ChannelEventRecorder
from main.app.domain.channel.whatsapp.bot.intake_handoff import WhatsAppIntakeHandoffService
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.handoff.tokens import (
    TOKEN_REJECTED_MESSAGE,
    HandoffTokenError,
)
from main.appodus_utils import Object
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

whatsapp_intake_router = APIRouter(prefix="/wa/intake", tags=["WhatsApp Intake"])
handoff_service: HandoffTokenService = di[HandoffTokenService]
intake_handoff_service: WhatsAppIntakeHandoffService = di[WhatsAppIntakeHandoffService]
channel_event_recorder: ChannelEventRecorder = di[ChannelEventRecorder]

# Same posture as the public redeem route: the token is a bearer credential, so the
# endpoint is throttled even though a token is unguessable.
_redeem_rate_limit = RateLimiter(scope="wa_intake_redeem", limit=30, window_seconds=60)


class SeededDraftDto(Object):
    """Where to send the customer: the draft their answers were written into."""

    verification_id: str


@whatsapp_intake_router.post("/{handoff_token}/redeem", response_model=SuccessResponse[SeededDraftDto])
async def redeem_intake(
    # Not `token`: the AuthJWT dependency declares a header parameter by that name, and
    # FastAPI merges the two into a path param it then refuses to build.
    handoff_token: str,
    request: Request,
    authorize: AuthJWT = Depends(),
    _: None = Depends(_redeem_rate_limit),
):
    """Spend an intake link and seed this customer's draft with the chat's answers.

    Answers **not-found** for every failure — expired, replayed, forged, wrong intent, or
    a conversation whose answers have already been used. One indistinguishable response,
    matching the other landings: "forbidden" would concede the link exists, and the
    frontend's shared HTTP client hard-navigates to `/forbidden` on any 403, replacing the
    recovery page the customer needs to see.
    """
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())

    try:
        claims = await handoff_service.redeem_intake(
            handoff_token, redeemed_ip=_client_ip(request)
        )
    except HandoffTokenError:
        raise ResourceNotFoundException(resource=TOKEN_REJECTED_MESSAGE)

    verification_id = await intake_handoff_service.seed_draft(claims.phone, customer_id)
    # The seam is crossed (§26.10, D80). The redemption ledger row was written before the
    # draft existed, and an `intake` token names a phone and nothing else (D71), so this is
    # the only moment the channel can tie a conversation to the verification it produced —
    # which is what later lets a payment be attributed to WhatsApp rather than to the web.
    await channel_event_recorder.record(
        WhatsAppChannelEventType.INTAKE_REDEEMED,
        phone_e164=claims.phone,
        verification_id=verification_id,
        customer_id=customer_id,
    )
    return SuccessResponse[SeededDraftDto](
        data=SeededDraftDto(verification_id=verification_id)
    )


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None
