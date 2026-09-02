"""Public handoff endpoints (PRD §7.4.2, §7.5). URL shape: /public/wa/handoff/...

**No JWT here** — the handoff token is the authorization, exactly as the share token is on
`public_share_router`. Every response is scoped to one action on one case.

The landing flow is two steps on purpose (D51). `redeem` spends the token's nonce once and
sets a short-lived grant cookie; the page then works on the grant, so a refresh or a
back-navigation does not burn the link while a forwarded copy of the token is already
dead. The grant is **not a session**: it is path-scoped, expires with the token it came
from, and authorizes one intent on one case.

Only `pay` acts on the grant alone (D50). `upload` and `report` return a portal
destination instead, because canonical evidence (§7.1.6) and the report link (Decision B)
must sit behind a real login rather than a forwardable link.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from kink import di

from main.app.domain.channel.whatsapp.handoff.grant import (
    clear_grant_cookie,
    read_grant,
    set_grant_cookie,
)
from main.app.domain.channel.whatsapp.consent.models import (
    SetWhatsAppConsentDto,
    WhatsAppConsentDto,
    WhatsAppConsentSource,
)
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.app.domain.channel.whatsapp.handoff.models import ACTION_INTENTS, HandoffIntent
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.handoff.tokens import (
    TOKEN_REJECTED_MESSAGE,
    HandoffTokenError,
)
from main.app.domain.channel.whatsapp.handoff.view_models import (
    HandoffContextDto,
    HandoffPaymentDto,
)
from main.app.domain.payment.models import PaymentMethodKind
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

handoff_router = APIRouter(prefix="/public/wa/handoff", tags=["WhatsApp Handoff"])
handoff_service: HandoffTokenService = di[HandoffTokenService]
verification_service: VerificationService = di[VerificationService]
payment_service: PaymentService = di[PaymentService]
whatsapp_consent_service: WhatsAppConsentService = di[WhatsAppConsentService]

# A handoff link is a bearer credential on a public endpoint, so the redeem route is
# throttled like the other unauthenticated sensitive routes — a token is unguessable, but
# an unbounded client should not be able to grind at the endpoint.
_redeem_rate_limit = RateLimiter(scope="wa_handoff_redeem", limit=30, window_seconds=60)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@handoff_router.post(
    "/{intent}/{token}/redeem", response_model=SuccessResponse[HandoffContextDto]
)
async def redeem(
    intent: HandoffIntent,
    token: str,
    request: Request,
    response: Response,
    _: None = Depends(_redeem_rate_limit),
):
    """Spend a handoff link and return the context its landing page must acknowledge.

    "Picking up where you left off" is a spec requirement (§7.4.2): silently losing the
    customer's context is a violation, not a cosmetic gap.
    """
    if intent not in ACTION_INTENTS:
        # `link` tokens are redeemed by the authenticated linking endpoints, never here:
        # this router hands out case context, and a link token names no case. Answering
        # not-found keeps the two token shapes from being probed against each other.
        raise ResourceNotFoundException(resource=TOKEN_REJECTED_MESSAGE)

    # A grant the caller already holds for this intent means they may be reloading the
    # page rather than replaying a forwarded link (D51).
    held = read_grant(request, intent)
    try:
        claims = await handoff_service.redeem(
            token,
            intent,
            redeemed_ip=_client_ip(request),
            holder_jti=held.jti if held else None,
        )
    except HandoffTokenError:
        # One response for every failure — expired, replayed, forged, wrong landing.
        # **Not-found, not forbidden**, matching how a revoked share token reads (§13.3).
        # "Forbidden" concedes that the link exists and someone else may use it; not-found
        # concedes nothing, which is the whole point of making failures indistinguishable.
        # It also keeps a dead link on its own recovery page: the shared HTTP client
        # hard-navigates the browser to /forbidden on any 403.
        raise ResourceNotFoundException(resource=TOKEN_REJECTED_MESSAGE)

    verification = await verification_service.get_by_id(claims.case)
    set_grant_cookie(response, claims)
    return SuccessResponse[HandoffContextDto](data=HandoffContextDto(
        intent=claims.intent,
        case_id=claims.case,
        vid=verification.vid,
        tier=verification.tier,
        status=verification.status,
        amount_due_minor=verification.price_locked_minor,
        currency=verification.currency,
        expires_at=claims.expires_at,
    ))


@handoff_router.post("/pay/initiate", response_model=SuccessResponse[HandoffPaymentDto])
async def initiate_payment(request: Request):
    """Start payment for the case the caller's grant names (§7.4.2, Decision A).

    The grant is the authorization; the case comes from it, never from the request body,
    so a holder of one link cannot pay against a different case.
    """
    grant = read_grant(request, HandoffIntent.PAY)
    if grant is None:
        raise ResourceNotFoundException(resource=TOKEN_REJECTED_MESSAGE)

    payment = await payment_service.initiate(
        grant.case_id, grant.customer_id, PaymentMethodKind.CARD,
        # One payment per handoff, so a double-submit on a flaky mobile connection
        # cannot open two charges for the same case.
        idempotency_key=f"wa-handoff-{grant.jti}",
    )
    return SuccessResponse[HandoffPaymentDto](data=HandoffPaymentDto(
        tx_ref=payment.tx_ref,
        checkout_url=payment.checkout_url,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
    ))


@handoff_router.put("/pay/consent", response_model=SuccessResponse[WhatsAppConsentDto])
async def set_consents(req: SetWhatsAppConsentDto, request: Request):
    """Record the §7.4.6 opt-ins from the payment landing (D76).

    This is the one moment a WhatsApp-native customer is asked. Without it they could opt
    in only by finding account settings on a site they arrived at from a chat link — and
    §7.10 counts the opt-in rate as the channel's consent asset.

    Grant-scoped exactly like `pay/initiate`: the customer id comes from the grant cookie,
    never from the request body, so a holder of one link cannot consent on someone else's
    behalf.
    """
    grant = read_grant(request, HandoffIntent.PAY)
    if grant is None:
        raise ResourceNotFoundException(resource=TOKEN_REJECTED_MESSAGE)

    consents = await whatsapp_consent_service.set_consents(
        grant.customer_id,
        req.utility,
        req.marketing,
        WhatsAppConsentSource.WA_PAY_LANDING,
    )
    return SuccessResponse[WhatsAppConsentDto](data=consents)


@handoff_router.post("/release", response_model=SuccessResponse[dict])
async def release(response: Response):
    """Drop the grant once its action is finished, so it does not outlive its purpose."""
    clear_grant_cookie(response)
    return SuccessResponse[dict](data={"released": True})
