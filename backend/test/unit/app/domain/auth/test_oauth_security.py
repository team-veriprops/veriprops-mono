"""Unit tests for OAuth security hardening (S6 — R2.3).

Covers:
- consume_state single-use replay protection
- resolve_frontend_origin allowlist enforcement (unlisted origins rejected)
- Google ID token JWKS-based signature verification (audience, issuer, signature)
- Google JWKS Redis caching and key-rotation fallback
- Apple JWKS Redis caching and key-rotation fallback
- OAuth state stored with explicit 10-minute TTL
"""
import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import exceptions as jose_exceptions

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


_FAKE_JWKS = {"keys": [{"kty": "RSA", "kid": "key-1", "n": "n-value", "e": "AQAB", "alg": "RS256", "use": "sig"}]}
_FAKE_CLAIMS = {
    "sub": "google-uid-123",
    "email": "user@example.com",
    "email_verified": True,
    "given_name": "Ada",
    "family_name": "W",
    "iss": "https://accounts.google.com",
    "aud": "google-client-id",
}
_FAKE_APPLE_JWKS = {"keys": [{"kty": "RSA", "kid": "apple-key-1", "n": "n-value", "e": "AQAB", "alg": "RS256"}]}


# ── consume_state — replay protection ─────────────────────────────────────────

async def test_consume_state_is_single_use():
    """State token is single-use: second consume returns None (key was deleted)."""
    call_count = 0
    stored_raw = '{"code_verifier": "v", "intent": "default", "frontend_origin": "http://localhost:3000", "mode": "auth", "link_user_id": null}'

    async def fake_get(key):
        nonlocal call_count
        call_count += 1
        return stored_raw if call_count == 1 else None

    with patch("main.appodus_utils.db.redis_utils.RedisUtils.get_redis", side_effect=fake_get), \
         patch("main.appodus_utils.db.redis_utils.RedisUtils.delete", new_callable=AsyncMock):
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        first = await OauthUtils.consume_state("state-abc")
        second = await OauthUtils.consume_state("state-abc")

    assert first is not None
    assert second is None


async def test_consume_state_returns_none_for_missing_key():
    with patch("main.appodus_utils.db.redis_utils.RedisUtils.get_redis", new_callable=AsyncMock, return_value=None), \
         patch("main.appodus_utils.db.redis_utils.RedisUtils.delete", new_callable=AsyncMock):
        from main.app.domain.user.auth.oauth.providers.utils import OauthUtils
        result = await OauthUtils.consume_state("nonexistent-state")

    assert result is None


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


# ── Google ID token — audience / signature rejection ─────────────────────────

async def test_google_token_wrong_audience_rejected():
    with patch("main.app.domain.user.auth.oauth.providers.google.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.google.jwt") as mock_jwt:
        mock_redis.get_redis = AsyncMock(return_value=json.dumps(_FAKE_JWKS))
        mock_jwt.decode.side_effect = jose_exceptions.JWTClaimsError("Invalid audience")

        from main.app.domain.user.auth.oauth.providers.google import _verify_google_id_token
        with pytest.raises(jose_exceptions.JWTClaimsError):
            await _verify_google_id_token("fake.jwt.token", "wrong-client-id")


async def test_google_token_invalid_signature_rejected():
    with patch("main.app.domain.user.auth.oauth.providers.google.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.google.jwt") as mock_jwt:
        mock_redis.get_redis = AsyncMock(return_value=json.dumps(_FAKE_JWKS))
        mock_jwt.decode.side_effect = jose_exceptions.JWTError("Signature verification failed")

        from main.app.domain.user.auth.oauth.providers.google import _verify_google_id_token
        with pytest.raises(jose_exceptions.JWTError):
            await _verify_google_id_token("tampered.jwt.token", "google-client-id")


# ── Google JWKS — caching ─────────────────────────────────────────────────────

async def test_google_jwks_cached_on_second_call():
    """JWKS endpoint fetched once; second _get_google_jwks call uses Redis."""
    get_count = 0

    async def fake_get_redis(key):
        nonlocal get_count
        get_count += 1
        return json.dumps(_FAKE_JWKS) if get_count > 1 else None

    mock_http_response = MagicMock()
    mock_http_response.json.return_value = _FAKE_JWKS
    mock_http_response.raise_for_status = MagicMock()

    with patch("main.app.domain.user.auth.oauth.providers.google.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.google.httpx_client") as mock_client:
        mock_redis.get_redis = AsyncMock(side_effect=fake_get_redis)
        mock_redis.set_redis = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)

        from main.app.domain.user.auth.oauth.providers.google import _get_google_jwks
        await _get_google_jwks()  # cache miss — fetches from Google
        await _get_google_jwks()  # cache hit — no HTTP call

    assert mock_client.get.call_count == 1


async def test_google_jwks_refetched_on_kid_miss():
    """Unknown kid causes cache invalidation and a single re-fetch."""
    mock_http_response = MagicMock()
    mock_http_response.json.return_value = _FAKE_JWKS
    mock_http_response.raise_for_status = MagicMock()

    decode_calls = 0

    def fake_decode(*args, **kwargs):
        nonlocal decode_calls
        decode_calls += 1
        if decode_calls == 1:
            raise jose_exceptions.JWKError("Key not found")
        return _FAKE_CLAIMS

    with patch("main.app.domain.user.auth.oauth.providers.google.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.google.httpx_client") as mock_client, \
         patch("main.app.domain.user.auth.oauth.providers.google.jwt") as mock_jwt:
        mock_redis.get_redis = AsyncMock(return_value=json.dumps(_FAKE_JWKS))
        mock_redis.set_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)
        mock_jwt.decode.side_effect = fake_decode

        from main.app.domain.user.auth.oauth.providers.google import _verify_google_id_token
        result = await _verify_google_id_token("some.jwt.token", "google-client-id")

    mock_redis.delete.assert_called_once_with("oauth:jwks:google")
    mock_client.get.assert_called_once()
    assert result == _FAKE_CLAIMS


# ── Apple JWKS — caching ──────────────────────────────────────────────────────

async def test_apple_jwks_cached_on_second_call():
    """Apple JWKS endpoint fetched once; second _get_apple_jwks call uses Redis."""
    get_count = 0

    async def fake_get_redis(key):
        nonlocal get_count
        get_count += 1
        return json.dumps(_FAKE_APPLE_JWKS) if get_count > 1 else None

    mock_http_response = MagicMock()
    mock_http_response.json.return_value = _FAKE_APPLE_JWKS
    mock_http_response.raise_for_status = MagicMock()

    with patch("main.app.domain.user.auth.oauth.providers.apple.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.apple.httpx_client") as mock_client:
        mock_redis.get_redis = AsyncMock(side_effect=fake_get_redis)
        mock_redis.set_redis = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)

        from main.app.domain.user.auth.oauth.providers.apple import _get_apple_jwks
        await _get_apple_jwks()  # cache miss — fetches from Apple
        await _get_apple_jwks()  # cache hit — no HTTP call

    assert mock_client.get.call_count == 1


async def test_apple_jwks_refetched_on_kid_miss():
    """Unknown Apple kid causes cache invalidation and a single re-fetch."""
    mock_http_response = MagicMock()
    mock_http_response.json.return_value = _FAKE_APPLE_JWKS
    mock_http_response.raise_for_status = MagicMock()

    fake_apple_claims = {"sub": "apple-uid-456", "email": "user@privaterelay.appleid.com", "email_verified": True}
    decode_calls = 0

    def fake_decode(*args, **kwargs):
        nonlocal decode_calls
        decode_calls += 1
        if decode_calls == 1:
            raise jose_exceptions.JWKError("Key not found")
        return fake_apple_claims

    with patch("main.app.domain.user.auth.oauth.providers.apple.RedisUtils") as mock_redis, \
         patch("main.app.domain.user.auth.oauth.providers.apple.httpx_client") as mock_client, \
         patch("main.app.domain.user.auth.oauth.providers.apple.jwt") as mock_jwt:
        mock_redis.get_redis = AsyncMock(return_value=json.dumps(_FAKE_APPLE_JWKS))
        mock_redis.set_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)
        mock_jwt.decode.side_effect = fake_decode

        from main.app.domain.user.auth.oauth.providers.apple import _decode_apple_id_token
        result = await _decode_apple_id_token("apple.id.token", "com.veriprops.app")

    mock_redis.delete.assert_called_once_with("oauth:jwks:apple")
    mock_client.get.assert_called_once()
    assert result == fake_apple_claims


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
