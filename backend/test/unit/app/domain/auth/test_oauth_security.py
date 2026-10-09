"""Unit tests for OAuth security hardening (S6 — R2.3).

Covers:
- consume_state single-use replay protection
- resolve_frontend_origin allowlist enforcement (unlisted origins rejected)
- Google and Apple ID tokens verified through the shared verifier (test_oauth_id_token.py)
- Apple's ES256 client secret
- OAuth state stored with explicit 10-minute TTL
"""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.appodus_utils.exception.exceptions import ForbiddenException


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(origin: str = None, referer: str = None):
    req = MagicMock()
    req.headers = {}
    if origin:
        req.headers["origin"] = origin
    if referer:
        req.headers["referer"] = referer
    return req


# ── consume_state — replay protection ─────────────────────────────────────────

_STORED_STATE = '{"code_verifier": "v", "intent": "default", "frontend_origin": "http://localhost:3000", "mode": "auth", "link_user_id": null}'


def _atomic_pop_store(initial: dict):
    """A store whose pop hands a value to exactly one caller, as GETDEL / DELETE … RETURNING do."""
    kv = dict(initial)

    async def fake_pop(key):
        return kv.pop(key, None)

    return fake_pop


async def test_consume_state_is_single_use():
    """State token is single-use: second consume returns None (key was consumed)."""
    fake_pop = _atomic_pop_store({"oauth:state:state-abc": _STORED_STATE})

    with patch("main.appodus_utils.db.redis_utils.RedisUtils.pop", side_effect=fake_pop):
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        from main.app.domain.user.auth.oauth.providers.models import OAuthRequestStoredState
        first = await OauthUtils.consume_state("state-abc")
        second = await OauthUtils.consume_state("state-abc")

    # RedisUtils returns UTF-8 text, so consume_state must rehydrate the JSON into
    # the typed model (the callback reads first.frontend_origin / .code_verifier).
    assert isinstance(first, OAuthRequestStoredState)
    assert first.frontend_origin == "http://localhost:3000"
    assert first.code_verifier == "v"
    assert second is None


async def test_consume_state_returns_none_for_missing_key():
    with patch("main.appodus_utils.db.redis_utils.RedisUtils.pop", new_callable=AsyncMock, return_value=None):
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        result = await OauthUtils.consume_state("nonexistent-state")

    assert result is None


async def test_concurrent_callbacks_consume_a_state_once():
    """Two callbacks racing with one state: exactly one gets it (the pop is atomic)."""
    import asyncio

    fake_pop = _atomic_pop_store({"oauth:state:state-race": _STORED_STATE})

    with patch("main.appodus_utils.db.redis_utils.RedisUtils.pop", side_effect=fake_pop):
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        results = await asyncio.gather(
            OauthUtils.consume_state("state-race"), OauthUtils.consume_state("state-race"),
        )

    assert sum(r is not None for r in results) == 1


# ── resolve_frontend_origin — allowlist ───────────────────────────────────────

async def test_resolve_frontend_origin_rejects_unlisted():
    """An explicit origin not on the allowlist must be rejected with ForbiddenException."""
    with patch("main.app.domain.user.auth.oauth.providers.utils.settings") as mock_settings:
        mock_settings.OAUTH_FRONTEND_ORIGINS = "http://localhost:3000,https://veriprops.ng"
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        req = _make_request(origin="https://evil.example.com")
        with pytest.raises(ForbiddenException):
            await OauthUtils.resolve_frontend_origin(req)


async def test_resolve_frontend_origin_accepts_listed():
    with patch("main.app.domain.user.auth.oauth.providers.utils.settings") as mock_settings:
        mock_settings.OAUTH_FRONTEND_ORIGINS = "http://localhost:3000,https://veriprops.ng"
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        req = _make_request(origin="https://veriprops.ng")
        result = await OauthUtils.resolve_frontend_origin(req)

    assert result == "https://veriprops.ng"


# ── Google / Apple — ID tokens go through the shared verifier ────────────────
# The verifier itself (key choice by kid, signature, audience, issuer, at_hash, key rotation)
# is tested with real keys in test_oauth_id_token.py.

async def test_google_verifies_against_its_keys_and_both_issuer_forms():
    from main.app.domain.user.auth.oauth.providers import google

    with patch.object(google, "verify_id_token", new_callable=AsyncMock, return_value={"sub": "g-1"}) as verify:
        claims = await google._verify_google_id_token("id.jwt", "access-1", "google-client-id")

    assert claims == {"sub": "g-1"}
    verify.assert_awaited_once_with(
        "id.jwt", google.GOOGLE_KEYS, audience="google-client-id",
        issuer=("accounts.google.com", "https://accounts.google.com"), access_token="access-1",
    )
    assert google.GOOGLE_KEYS.cache_key == "oauth:jwks:google"


async def test_apple_verifies_against_its_keys_and_issuer():
    from main.app.domain.user.auth.oauth.providers import apple

    with patch.object(apple, "verify_id_token", new_callable=AsyncMock, return_value={"sub": "a-1"}) as verify:
        await apple._decode_apple_id_token("id.jwt", "access-1", "com.veriprops.app")

    verify.assert_awaited_once_with(
        "id.jwt", apple.APPLE_KEYS, audience="com.veriprops.app",
        issuer="https://appleid.apple.com", access_token="access-1",
    )
    assert apple.APPLE_KEYS.cache_key == "oauth:jwks:apple"


async def test_apples_client_secret_is_an_es256_jwt_under_the_teams_key_id():
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from main.app.domain.user.auth.oauth.providers import apple
    from main.app.domain.user.auth.oauth.providers.models import OAuthCallbackRequestDto

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    provider = object.__new__(apple.AppleAuthProvider)
    provider._client_id, provider._iss, provider._private_key, provider._key_id = (
        "com.veriprops.app", "TEAM123", pem, "KEY123",
    )
    token_response = MagicMock()
    token_response.json.return_value = {"id_token": "id.jwt", "access_token": "access-1"}
    token_response.raise_for_status = MagicMock()

    with patch.object(apple, "httpx_client") as client, \
         patch.object(apple, "_decode_apple_id_token", new_callable=AsyncMock,
                      return_value={"sub": "a-1", "email": "a@privaterelay.appleid.com", "email_verified": True}):
        client.post = AsyncMock(return_value=token_response)
        await provider.verify(OAuthCallbackRequestDto(code="c", redirect_uri="https://x/cb", code_verifier="v"), _make_request())

    secret = client.post.call_args.kwargs["data"]["client_secret"]
    assert jwt.get_unverified_header(secret) == {"alg": "ES256", "kid": "KEY123", "typ": "JWT"}
    claims = jwt.decode(secret, key.public_key(), algorithms=["ES256"], audience="https://appleid.apple.com")
    assert (claims["iss"], claims["sub"]) == ("TEAM123", "com.veriprops.app")


# ── OAuth state TTL ───────────────────────────────────────────────────────────

async def test_state_stored_with_ten_minute_ttl():
    """OAuth state must be stored with a 10-minute TTL to bound the replay window."""
    mock_set = AsyncMock()

    with patch("main.app.domain.user.auth.oauth.providers.utils.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.utils.JwtAuthUtils") as mock_jwt_utils, \
         patch("main.app.domain.user.auth.oauth.providers.utils.OauthUtils.resolve_frontend_origin",
               new_callable=AsyncMock, return_value="http://localhost:3000"), \
         patch("main.app.domain.user.auth.oauth.providers.utils.OauthUtils.callback_redirect_uri",
               new_callable=AsyncMock, return_value="http://localhost:8000/callback"):
        mock_redis.set_redis = mock_set
        mock_jwt_utils.generate_pkce.return_value = ("challenge", "verifier", "state-xyz")

        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider

        await OauthUtils.init_0auth(
            platform=SocialAuthProvider.GOOGLE,
            request=_make_request(),
            base_url="https://accounts.google.com/o/oauth2/v2/auth",
            client_id="client-id",
            scope="openid email profile",
        )

    state_call = next(
        c for c in mock_set.call_args_list if "oauth:state:" in str(c.args[0])
    )
    assert state_call.kwargs.get("time_to_live") == timedelta(minutes=10)


async def test_oauth_state_round_trips_through_text_store():
    """init_0auth must persist the state as JSON text (RedisUtils stores UTF-8 only),
    and consume_state must rehydrate that exact text into the typed model — storing
    the model object instead round-trips as a bare string and breaks the callback."""
    kv: dict[str, str] = {}

    async def fake_set(key, value, time_to_live=None, *, strict=False):
        # A state that was never stored would only fail at the callback, so it is written strictly.
        assert strict is True
        kv[key] = value

    async def fake_pop(key):
        return kv.pop(key, None)

    with patch("main.appodus_utils.db.redis_utils.RedisUtils.set_redis", side_effect=fake_set), \
         patch("main.appodus_utils.db.redis_utils.RedisUtils.pop", side_effect=fake_pop), \
         patch("main.app.domain.user.auth.oauth.providers.utils.JwtAuthUtils") as mock_jwt_utils, \
         patch("main.app.domain.user.auth.oauth.providers.utils.OauthUtils.resolve_frontend_origin",
               new_callable=AsyncMock, return_value="http://localhost:3000"), \
         patch("main.app.domain.user.auth.oauth.providers.utils.OauthUtils.callback_redirect_uri",
               new_callable=AsyncMock, return_value="http://localhost:8000/callback"):
        mock_jwt_utils.generate_pkce.return_value = ("challenge", "verifier", "state-xyz")

        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        from main.app.domain.user.auth.oauth.providers.models import (
            OAuthRequestStoredState,
            SocialAuthProvider,
        )

        await OauthUtils.init_0auth(
            platform=SocialAuthProvider.GOOGLE,
            request=_make_request(),
            base_url="https://accounts.google.com/o/oauth2/v2/auth",
            client_id="client-id",
            scope="openid email profile",
        )
        # Stored value must be serialized text, never the model object.
        assert isinstance(kv["oauth:state:state-xyz"], str)

        restored = await OauthUtils.consume_state("state-xyz")

    assert isinstance(restored, OAuthRequestStoredState)
    assert restored.frontend_origin == "http://localhost:3000"
    assert restored.code_verifier == "verifier"
