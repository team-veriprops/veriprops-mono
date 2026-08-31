"""Handoff token service (PRD §7.5, WA-14/WA-28).

A bearer token that travels through WhatsApp, where forwarding a message is the norm.
The threat model is explicit in the PRD: a forwarded or leaked message must expose at
most one expired, single-use, single-action link — never an account. These are the tests
that hold that line, so they are written adversarially rather than happy-path first.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from jose import jwt

from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.tokens import (
    HANDOFF_ALGORITHM,
    HandoffTokenError,
    decode_handoff_token,
    handoff_keys,
    issue_handoff_token,
)
from main.appodus_utils import Utils

CASE_ID = "ca5e00000000000000000000000000ab"
CUSTOMER_ID = "11111111-2222-3333-4444-555555555555"


def token(**over):
    kwargs = dict(customer_id=CUSTOMER_ID, case_id=CASE_ID, intent=HandoffIntent.PAY)
    kwargs.update(over)
    return issue_handoff_token(**kwargs)


class TestClaims:
    def test_carries_exactly_the_claims_the_spec_names(self):
        claims = decode_handoff_token(token())
        assert claims.sub == CUSTOMER_ID
        assert claims.case == CASE_ID
        assert claims.intent == HandoffIntent.PAY
        assert claims.jti

    def test_expires_fifteen_minutes_after_issue(self):
        claims = decode_handoff_token(token())
        assert timedelta(minutes=14) <= (claims.expires_at - claims.issued_at) <= timedelta(minutes=16)

    def test_each_token_carries_a_distinct_nonce(self):
        # The jti is the single-use key: a repeat would let one redemption kill another.
        assert len({decode_handoff_token(token()).jti for _ in range(25)}) == 25


class TestSignature:
    def test_is_signed_asymmetrically(self):
        # §7.5 pins RS256: only the backend can mint, and verification needs no secret.
        assert jwt.get_unverified_header(token())["alg"] == HANDOFF_ALGORITHM == "RS256"

    def test_rejects_a_tampered_payload(self):
        header, payload, signature = token().split(".")
        forged = issue_handoff_token(
            customer_id=CUSTOMER_ID, case_id="0ther000000000000000000000000000",
            intent=HandoffIntent.PAY,
        ).split(".")[1]
        with pytest.raises(HandoffTokenError):
            decode_handoff_token(f"{header}.{forged}.{signature}")

    def test_rejects_a_token_signed_with_a_different_key(self):
        other = jwt.encode(
            {"sub": CUSTOMER_ID, "case": CASE_ID, "intent": HandoffIntent.PAY.value,
             "jti": "x", "exp": Utils.datetime_now() + timedelta(minutes=5)},
            _throwaway_private_key(), algorithm=HANDOFF_ALGORITHM,
        )
        with pytest.raises(HandoffTokenError):
            decode_handoff_token(other)

    def test_rejects_an_algorithm_confusion_attempt(self):
        # The classic attack: re-sign with HS256 using the *public* key as the HMAC
        # secret, so a verifier that trusts the header's `alg` validates it happily.
        # Forged by hand rather than through the JWT library, because the library
        # refuses to HMAC with a PEM — relying on that would test its guard, not our
        # pinning, and would pass even if we accepted any algorithm.
        forged = _forge_hs256(
            {"sub": CUSTOMER_ID, "case": CASE_ID, "intent": HandoffIntent.PAY.value,
             "jti": "x", "exp": int((Utils.datetime_now() + timedelta(minutes=5)).timestamp()),
             "iat": int(Utils.datetime_now().timestamp())},
            secret=handoff_keys().public_key,
        )
        with pytest.raises(HandoffTokenError):
            decode_handoff_token(forged)

    def test_rejects_an_unsigned_token(self):
        with pytest.raises(HandoffTokenError):
            decode_handoff_token("not.a.token")
        with pytest.raises(HandoffTokenError):
            decode_handoff_token("")


class TestExpiry:
    def test_rejects_an_expired_token(self):
        expired = issue_handoff_token(
            customer_id=CUSTOMER_ID, case_id=CASE_ID, intent=HandoffIntent.PAY,
            ttl=timedelta(seconds=-1),
        )
        with pytest.raises(HandoffTokenError):
            decode_handoff_token(expired)


class TestScope:
    def test_a_token_is_scoped_to_one_intent(self):
        # §7.5: the token authorizes the named action on the named case, nothing else.
        claims = decode_handoff_token(token(intent=HandoffIntent.UPLOAD))
        assert claims.intent == HandoffIntent.UPLOAD
        with pytest.raises(HandoffTokenError):
            claims.assert_scope(HandoffIntent.PAY, CASE_ID)

    def test_a_token_is_scoped_to_one_case(self):
        claims = decode_handoff_token(token())
        with pytest.raises(HandoffTokenError):
            claims.assert_scope(HandoffIntent.PAY, "0ther000000000000000000000000000")

    def test_accepts_its_own_intent_and_case(self):
        decode_handoff_token(token()).assert_scope(HandoffIntent.PAY, CASE_ID)

    def test_an_unknown_intent_is_refused_rather_than_coerced(self):
        forged = jwt.encode(
            {"sub": CUSTOMER_ID, "case": CASE_ID, "intent": "admin", "jti": "x",
             "exp": Utils.datetime_now() + timedelta(minutes=5)},
            handoff_keys().private_key, algorithm=HANDOFF_ALGORITHM,
        )
        with pytest.raises(HandoffTokenError):
            decode_handoff_token(forged)

    def test_is_not_a_session(self):
        # Completing the action must never log anyone in, so the token deliberately
        # carries no role, persona, or session claim to be mistaken for one.
        payload = jwt.get_unverified_claims(token())
        assert set(payload) == {"sub", "case", "intent", "jti", "exp", "iat"}


def _forge_hs256(payload: dict, secret: str) -> str:
    """Hand-build an HS256 JWS — the shape an algorithm-confusion attacker sends."""
    import base64
    import hashlib
    import hmac
    import json

    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = b".".join((
        b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()),
        b64(json.dumps(payload).encode()),
    ))
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return b".".join((signing_input, b64(signature))).decode()


def _throwaway_private_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
