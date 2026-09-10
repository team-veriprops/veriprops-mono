"""Handoff token minting and verification (PRD §26.5).

These tokens travel through WhatsApp, where forwarding a message is ordinary behaviour,
so the PRD's threat model is the design brief: a leaked or forwarded link must expose at
most one expired, single-use, single-action grant — never an account.

Three properties do that work, and each is enforced here rather than at a call site:

* **RS256, verified against a pinned algorithm.** Reading ``alg`` from the token's own
  header is the classic algorithm-confusion hole (re-sign with HS256 using the public key
  as the HMAC secret); ``decode`` is pinned so a forged header is simply not a valid token.
* **A 15-minute life**, so a forwarded message goes stale on its own.
* **A closed intent set**, so a token claiming anything else is not a token at all.

Single-use lives in the redemption ledger next door — a nonce only means something once
something claims it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError, model_validator

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.handoff.models import ACTION_INTENTS, HandoffIntent
from main.appodus_utils import Utils
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER, Environment

# §26.5 pins the algorithm. Never widen this, and never let a token's own header choose.
HANDOFF_ALGORITHM = "RS256"
HANDOFF_TOKEN_TTL = timedelta(minutes=15)


# One message for every rejection. Expired, replayed, tampered, wrong-intent, and
# wrong-case must be indistinguishable from outside, or a prober can classify a link by
# reading the differences back.
TOKEN_REJECTED_MESSAGE = "This link is no longer valid."


class HandoffTokenError(Exception):
    """A token that cannot be trusted, for any reason.

    Deliberately undifferentiated: the reason is logged, never returned. Raise it without
    an argument so every rejection reads identically to the caller.
    """

    def __init__(self, message: str = TOKEN_REJECTED_MESSAGE):
        super().__init__(message)


class HandoffClaims(BaseModel):
    """The verified contents of a handoff token.

    Two shapes, held apart by the validator below (D55): an **action** token names a
    customer and a case; a **phone-scoped** token (`link`, `intake`) names a number that
    has no account yet. Neither can wear the other's claims, so a token minted to identify
    a stranger can never be replayed as authority over someone's case.
    """

    sub: Optional[str] = None      # customer id — action tokens only
    case: Optional[str] = None     # verification id — action tokens only
    phone: Optional[str] = None    # E.164 number — phone-scoped tokens only
    intent: HandoffIntent
    jti: str
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _claims_match_the_intent(self) -> "HandoffClaims":
        if self.intent in ACTION_INTENTS:
            if not self.sub or not self.case or self.phone:
                raise ValueError("action token must name a customer and a case, and no phone")
        elif not self.phone or self.sub or self.case:
            raise ValueError("phone-scoped token must name a phone, and no customer or case")
        return self

    def assert_scope(self, intent: HandoffIntent, case_id: str) -> None:
        """Confirm this token authorizes *intent* on *case_id* — and nothing else."""
        if self.intent != intent or self.case != case_id:
            raise HandoffTokenError()

    def assert_link_scope(self, phone_e164: str) -> None:
        """Confirm this token was minted to identify *phone_e164* — and nothing else."""
        if self.intent != HandoffIntent.LINK or self.phone != phone_e164:
            raise HandoffTokenError()

    def assert_phone_scope(self, intent: HandoffIntent, phone_e164: str) -> None:
        """Confirm this token carries *intent* for *phone_e164* — and nothing else.

        The general form of `assert_link_scope`, for the second phone-scoped intent
        (D71). Kept separate rather than widening the link check, because "this is a
        linking token" is an assertion the linking flow should keep making explicitly.
        """
        if self.intent != intent or self.phone != phone_e164:
            raise HandoffTokenError()


class HandoffKeys(BaseModel):
    private_key: str
    public_key: str


_ephemeral_keys: Optional[HandoffKeys] = None


def _generate_ephemeral_keys() -> HandoffKeys:
    """A per-process keypair for local development and automated runs.

    Handoff links are short-lived by design, so a keypair that dies with the process
    costs nothing outside production — and it means a developer or a CI job needs no key
    material to exercise the whole flow. Production and staging never reach this path:
    they fail closed instead.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return HandoffKeys(private_key=private_pem, public_key=public_pem)


def _is_configured(value: Optional[str]) -> bool:
    return bool((value or "").strip()) and (value or "").strip() != SECRET_PLACEHOLDER


def handoff_keys() -> HandoffKeys:
    """The signing keypair: configured material, or an ephemeral pair outside production."""
    global _ephemeral_keys

    private_key = settings.WHATSAPP_HANDOFF_PRIVATE_KEY
    public_key = settings.WHATSAPP_HANDOFF_PUBLIC_KEY
    if _is_configured(private_key) and _is_configured(public_key):
        # A PEM survives a one-line env var as literal backslash-n; restore it.
        return HandoffKeys(
            private_key=private_key.replace("\\n", "\n"),
            public_key=public_key.replace("\\n", "\n"),
        )

    if settings.ENVIRONMENT in (Environment.PRODUCTION, Environment.STAGING):
        raise HandoffTokenError(
            "WHATSAPP_HANDOFF_PRIVATE_KEY / WHATSAPP_HANDOFF_PUBLIC_KEY are not "
            f"configured in {settings.ENVIRONMENT.value}. Refusing to sign handoff links "
            "with a generated key that dies with the process."
        )

    if _ephemeral_keys is None:
        _ephemeral_keys = _generate_ephemeral_keys()
    return _ephemeral_keys


def issue_handoff_token(
    customer_id: str,
    case_id: str,
    intent: HandoffIntent,
    ttl: timedelta = HANDOFF_TOKEN_TTL,
) -> str:
    """Mint a token authorizing *intent* on *case_id* for *customer_id*.

    The payload carries nothing beyond the §26.5 claims — no role, persona, or session
    marker that a later reader could mistake for proof of login.
    """
    if intent not in ACTION_INTENTS:
        # A link token names no case; minting one here would produce a token whose
        # claims contradict its intent, and decode would refuse it anyway.
        raise HandoffTokenError()
    return _encode({"sub": customer_id, "case": case_id, "intent": intent.value}, ttl)


def issue_link_token(phone_e164: str, ttl: timedelta = HANDOFF_TOKEN_TTL) -> str:
    """Mint a token identifying *phone_e164* for the §26.4.4 WhatsApp→web linking flow.

    Deliberately weaker than an action token, because it is handed to a number we cannot
    yet attribute to anyone: it names no customer and no case, so on its own it unlocks
    nothing. Proving the number still requires the OTP that follows — the token only
    carries *which* number is being claimed across to the website, single-use, so a
    forwarded copy cannot start a second linking attempt.
    """
    return _encode({"phone": phone_e164, "intent": HandoffIntent.LINK.value}, ttl)


def issue_intake_token(phone_e164: str, ttl: timedelta = HANDOFF_TOKEN_TTL) -> str:
    """Mint a token carrying a chat intake across to the website (§5.1, D69/D71).

    Names the number and nothing else: the answers the bot collected stay on the bot
    session and are read at redemption. That keeps the URL short enough for a chat
    message and means a forwarded link carries no one's property details — it can only
    be spent, once, by whoever opens it first, and spending it still requires signing in
    before anything is created.
    """
    return _encode({"phone": phone_e164, "intent": HandoffIntent.INTAKE.value}, ttl)


def _encode(claims: dict, ttl: timedelta) -> str:
    """Sign *claims* with the standard nonce and lifetime.

    Only the keys a shape actually uses are emitted, so an action token has no `phone`
    key to confuse and a link token has no `case` key to be probed for.
    """
    issued_at = Utils.datetime_now()
    return jwt.encode(
        {
            **claims,
            # CSPRNG, per the repo-wide token rule — never uuid7 or random.
            "jti": Utils.random_str(32),
            "iat": issued_at,
            "exp": issued_at + ttl,
        },
        handoff_keys().private_key,
        algorithm=HANDOFF_ALGORITHM,
    )


def decode_handoff_token(token: str) -> HandoffClaims:
    """Verify a token and return its claims, or raise ``HandoffTokenError``."""
    try:
        payload = jwt.decode(
            token,
            handoff_keys().public_key,
            # Pinned: the token's own header never selects the algorithm.
            algorithms=[HANDOFF_ALGORITHM],
        )
    except JWTError as exc:
        raise HandoffTokenError() from exc

    try:
        intent = HandoffIntent(payload["intent"])
        return HandoffClaims(
            sub=payload.get("sub"),
            case=payload.get("case"),
            phone=payload.get("phone"),
            intent=intent,
            jti=payload["jti"],
            issued_at=_as_datetime(payload["iat"]),
            expires_at=_as_datetime(payload["exp"]),
        )
    except (KeyError, ValidationError, ValueError) as exc:
        # A well-signed token whose claims we do not recognise is still not one we will
        # act on — an unknown intent must never be coerced into a known one, and a token
        # whose claims contradict its intent (a `link` naming a case, say) is refused
        # rather than read for whichever half looks usable.
        raise HandoffTokenError() from exc


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromtimestamp(int(value), tz=timezone.utc)
