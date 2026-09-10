"""The action grant a redeemed handoff link leaves behind (PRD §26.5, D51).

The grant exists so a landing page survives a refresh without the link surviving a
forward. These tests hold both halves of that: it must work for the customer who redeemed
it, and it must be useless for anything other than the one action it names.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from jose import jwt

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.handoff.grant import (
    GRANT_COOKIE_PATH,
    clear_grant_cookie,
    read_grant,
    set_grant_cookie,
)
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.tokens import (
    HANDOFF_ALGORITHM,
    HandoffClaims,
    handoff_keys,
)
from main.appodus_utils import Utils

CASE_ID = "ca5e00000000000000000000000000ab"
CUSTOMER_ID = "11111111-2222-3333-4444-555555555555"


class _Response:
    """Minimal stand-in capturing what a real Response would send to the browser."""

    def __init__(self):
        self.cookies = {}
        self.deleted = []

    def set_cookie(self, key, value, **kwargs):
        self.cookies[key] = SimpleNamespace(value=value, **kwargs)

    def delete_cookie(self, key, **kwargs):
        self.deleted.append((key, kwargs))


def _request(cookies: dict):
    return SimpleNamespace(cookies=cookies)


def _claims(intent=HandoffIntent.PAY, case=CASE_ID, minutes=15) -> HandoffClaims:
    now = Utils.datetime_now()
    return HandoffClaims(
        sub=CUSTOMER_ID, case=case, intent=intent, jti=Utils.random_str(32),
        issued_at=now, expires_at=now + timedelta(minutes=minutes),
    )


def _issue(intent=HandoffIntent.PAY, case=CASE_ID, minutes=15):
    response = _Response()
    set_grant_cookie(response, _claims(intent=intent, case=case, minutes=minutes))
    [(name, cookie)] = response.cookies.items()
    return name, cookie


class TestCookieContainment:
    def test_is_http_only_so_page_script_can_never_read_it(self):
        _, cookie = _issue()
        assert cookie.httponly is True

    def test_is_scoped_to_the_handoff_endpoints_only(self):
        # A grant the browser never attaches elsewhere cannot become an ambient credential.
        _, cookie = _issue()
        assert cookie.path == GRANT_COOKIE_PATH

    def test_follows_the_deployment_secure_cookie_policy(self):
        _, cookie = _issue()
        assert cookie.secure == settings.AUTHJWT_COOKIE_SECURE

    def test_uses_lax_same_site_because_the_customer_arrives_from_whatsapp(self):
        # Strict would drop the cookie on exactly the cross-site journey this serves.
        _, cookie = _issue()
        assert cookie.samesite == "lax"

    def test_expires_with_the_token_that_produced_it(self):
        _, cookie = _issue(minutes=15)
        assert 14 * 60 <= cookie.max_age <= 15 * 60

    def test_release_clears_it_on_the_same_path(self):
        # A mismatched path would leave the cookie in place — deletion is path-sensitive.
        response = _Response()
        clear_grant_cookie(response)
        [(_, kwargs)] = response.deleted
        assert kwargs["path"] == GRANT_COOKIE_PATH


class TestReadGrant:
    def test_reads_back_the_action_it_was_issued_for(self):
        name, cookie = _issue()
        grant = read_grant(_request({name: cookie.value}), HandoffIntent.PAY)
        assert grant is not None
        assert grant.case_id == CASE_ID
        assert grant.customer_id == CUSTOMER_ID

    def test_a_grant_for_one_action_does_not_satisfy_another(self):
        # Holding an upload grant must not let the holder start a payment.
        name, cookie = _issue(intent=HandoffIntent.UPLOAD)
        assert read_grant(_request({name: cookie.value}), HandoffIntent.PAY) is None

    def test_no_cookie_means_no_grant(self):
        assert read_grant(_request({}), HandoffIntent.PAY) is None

    def test_an_expired_grant_is_refused(self):
        name, cookie = _issue(minutes=-1)
        assert read_grant(_request({name: cookie.value}), HandoffIntent.PAY) is None

    def test_a_forged_grant_is_refused(self):
        # Signed with the same keypair as the token, so forging one is no easier than
        # forging the link itself.
        forged = jwt.encode(
            {"jti": "x", "case": CASE_ID, "sub": CUSTOMER_ID,
             "intent": HandoffIntent.PAY.value,
             "exp": Utils.datetime_now() + timedelta(minutes=10)},
            _throwaway_private_key(), algorithm=HANDOFF_ALGORITHM,
        )
        name, _ = _issue()
        assert read_grant(_request({name: forged}), HandoffIntent.PAY) is None

    def test_garbage_is_refused_rather_than_raising(self):
        name, _ = _issue()
        for junk in ("", "not-a-jwt", "a.b.c"):
            assert read_grant(_request({name: junk}), HandoffIntent.PAY) is None

    def test_carries_no_session_material(self):
        # Completing the action must never amount to logging in (§26.5).
        _, cookie = _issue()
        payload = jwt.get_unverified_claims(cookie.value)
        assert set(payload) == {"jti", "case", "sub", "intent", "exp"}


def _throwaway_private_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def test_the_grant_is_signed_with_the_handoff_keypair():
    _, cookie = _issue()
    assert jwt.decode(cookie.value, handoff_keys().public_key, algorithms=[HANDOFF_ALGORITHM])
