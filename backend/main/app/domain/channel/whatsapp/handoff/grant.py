"""The short-lived action grant a redeemed handoff link leaves behind (PRD §26.5, D51).

§26.5 says the nonce is recorded on redemption and replays are rejected. Taken literally
that burns the link on the first page load — a refresh, a back-navigation, or WhatsApp's
own link-preview fetch would be enough. So the token is spent exactly once and hands the
browser a grant: the page works on the grant, the customer can reload, and a forwarded
copy of the token is already dead.

The grant is deliberately **not a session**:

* it names one intent and one case, and nothing reads it for anything else;
* it expires with the token it came from — no refresh, no extension;
* it is path-scoped to the handoff endpoints, so it is not even sent anywhere else;
* it carries no role or persona, so completing a payment cannot be mistaken for a login.

It is signed with the same RS256 keypair as the token, so a grant cannot be forged any
more easily than the link that produced it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.tokens import (
    HANDOFF_ALGORITHM,
    HandoffClaims,
    handoff_keys,
)
from main.appodus_utils import Utils

GRANT_COOKIE_NAME = "__Host-wa_grant"
# Scoped to the handoff endpoints only: the browser will not attach it to any other
# request, so it cannot be mistaken for — or used as — an ambient credential.
# NOTE: `__Host-` requires Path=/, so the name drops the prefix when the path narrows.
GRANT_COOKIE_PATH = "/api/public/wa/handoff"


class HandoffGrant(BaseModel):
    """One action, on one case, until the originating token would have expired."""

    jti: str
    case_id: str
    customer_id: str
    intent: HandoffIntent
    expires_at: datetime


def _cookie_name() -> str:
    # `__Host-` is only honoured with Path=/, and a path-scoped cookie is the stronger
    # containment here — a grant that is never sent to other endpoints cannot leak into
    # them. Browsers reject a `__Host-` cookie with a narrower path outright.
    return GRANT_COOKIE_NAME.removeprefix("__Host-")


def set_grant_cookie(response: Response, claims: HandoffClaims) -> None:
    """Hand the browser a grant for the action this token just authorized."""
    payload = jwt.encode(
        {
            "jti": claims.jti,
            "case": claims.case,
            "sub": claims.sub,
            "intent": claims.intent.value,
            "exp": claims.expires_at,
        },
        handoff_keys().private_key,
        algorithm=HANDOFF_ALGORITHM,
    )
    max_age = max(int((claims.expires_at - Utils.datetime_now()).total_seconds()), 0)
    response.set_cookie(
        key=_cookie_name(),
        value=payload,
        max_age=max_age,
        path=GRANT_COOKIE_PATH,
        httponly=True,
        secure=settings.AUTHJWT_COOKIE_SECURE,
        # Lax, not Strict: the customer arrives from WhatsApp, which is a cross-site
        # navigation. Strict would drop the cookie on exactly the journey this exists for.
        samesite="lax",
    )


def clear_grant_cookie(response: Response) -> None:
    response.delete_cookie(key=_cookie_name(), path=GRANT_COOKIE_PATH)


def read_grant(request: Request, intent: HandoffIntent) -> Optional[HandoffGrant]:
    """The caller's grant for *intent*, or ``None`` if it is absent, expired, or forged."""
    raw = request.cookies.get(_cookie_name())
    if not raw:
        return None

    try:
        payload = jwt.decode(raw, handoff_keys().public_key, algorithms=[HANDOFF_ALGORITHM])
        grant = HandoffGrant(
            jti=payload["jti"],
            case_id=payload["case"],
            customer_id=payload["sub"],
            intent=HandoffIntent(payload["intent"]),
            expires_at=payload["exp"],
        )
    except (JWTError, KeyError, ValueError):
        return None

    # A grant for one action never satisfies another, even for the same case.
    return grant if grant.intent == intent else None
