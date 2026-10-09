"""OpenID Connect ID-token verification shared by Google and Apple sign-in (S6 — R2.3).

Signed with real RSA keys, so these exercise the library's actual checks rather than a mock:
the signing key is chosen by the token's `kid` from the provider's published key set, the
signature, audience and issuer must all hold, and an `at_hash` claim must match the access
token it came with. A `kid` missing from the cached key set means the provider rotated its
keys: the cache is dropped and the set fetched once more.
"""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from main.app.domain.user.auth.oauth.providers import id_token as id_token_module
from main.app.domain.user.auth.oauth.providers.id_token import (
    JwksCache,
    SigningKeyNotFound,
    decode_id_token,
    verify_id_token,
)

AUDIENCE = "client-id"
ISSUER = "https://issuer.example"


def _keypair(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    return private, {**public_jwk, "kid": kid, "alg": "RS256", "use": "sig"}


KEY_1, JWK_1 = _keypair("key-1")
KEY_2, JWK_2 = _keypair("key-2")
JWKS = {"keys": [JWK_1]}


def _at_hash(access_token: str) -> str:
    digest = hashlib.sha256(access_token.encode()).digest()
    return base64.urlsafe_b64encode(digest[: len(digest) // 2]).rstrip(b"=").decode()


def _token(key=KEY_1, kid="key-1", **claims) -> str:
    now = datetime.now(timezone.utc)
    body = {"sub": "uid-1", "aud": AUDIENCE, "iss": ISSUER, "iat": now, "exp": now + timedelta(minutes=5), **claims}
    return jwt.encode(body, key, algorithm="RS256", headers={"kid": kid})


class TestDecode:
    def test_a_valid_token_yields_its_claims(self):
        claims = decode_id_token(_token(), JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)
        assert claims["sub"] == "uid-1"

    def test_any_of_several_accepted_issuers_passes(self):
        # Google signs with either the bare or the https form of its issuer.
        token = _token(iss="accounts.google.com")
        claims = decode_id_token(token, JWKS, audience=AUDIENCE,
                                 issuer=["accounts.google.com", "https://accounts.google.com"], access_token=None)
        assert claims["iss"] == "accounts.google.com"

    @pytest.mark.parametrize("claims", [{"aud": "someone-else"}, {"iss": "https://evil.example"}],
                             ids=["audience", "issuer"])
    def test_a_token_for_another_client_or_issuer_is_refused(self, claims):
        with pytest.raises(jwt.InvalidTokenError):
            decode_id_token(_token(**claims), JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_a_token_signed_by_another_key_under_a_known_kid_is_refused(self):
        forged = _token(key=KEY_2, kid="key-1")
        with pytest.raises(jwt.InvalidSignatureError):
            decode_id_token(forged, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_an_expired_token_is_refused(self):
        stale = _token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_id_token(stale, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_an_unknown_kid_is_reported_as_a_missing_key(self):
        with pytest.raises(SigningKeyNotFound):
            decode_id_token(_token(key=KEY_2, kid="key-2"), JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_the_algorithm_is_pinned_whatever_the_header_says(self):
        hs = jwt.encode({"sub": "x", "aud": AUDIENCE, "iss": ISSUER}, "secret-secret-secret-secret-32b!",
                        algorithm="HS256", headers={"kid": "key-1"})
        with pytest.raises(jwt.InvalidTokenError):
            decode_id_token(hs, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_a_matching_at_hash_passes(self):
        token = _token(at_hash=_at_hash("access-1"))
        assert decode_id_token(token, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token="access-1")

    def test_an_at_hash_for_another_access_token_is_refused(self):
        token = _token(at_hash=_at_hash("access-1"))
        with pytest.raises(jwt.InvalidTokenError, match="at_hash"):
            decode_id_token(token, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token="access-2")

    def test_an_at_hash_with_no_access_token_to_compare_is_refused(self):
        token = _token(at_hash=_at_hash("access-1"))
        with pytest.raises(jwt.InvalidTokenError, match="at_hash"):
            decode_id_token(token, JWKS, audience=AUDIENCE, issuer=ISSUER, access_token=None)

    def test_a_token_without_at_hash_needs_no_access_token(self):
        assert decode_id_token(_token(), JWKS, audience=AUDIENCE, issuer=ISSUER, access_token="access-1")


def _http_returning(*key_sets):
    responses = []
    for key_set in key_sets:
        response = MagicMock()
        response.json.return_value = key_set
        response.raise_for_status = MagicMock()
        responses.append(response)
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    return client


class TestJwksCache:
    async def test_the_key_set_is_fetched_once_then_served_from_the_cache(self):
        store = {}

        async def _get(key):
            return store.get(key)

        async def _set(key, value, time_to_live=None):
            store[key] = value

        client = _http_returning(JWKS)
        with patch.object(id_token_module, "RedisUtils") as redis, \
             patch.object(id_token_module, "_http", return_value=client):
            redis.get_redis = AsyncMock(side_effect=_get)
            redis.set_redis = AsyncMock(side_effect=_set)
            cache = JwksCache("https://issuer.example/keys", "oauth:jwks:test")
            assert await cache.get() == JWKS
            assert await cache.get() == JWKS

        assert client.get.await_count == 1


class TestVerifyWithRotation:
    async def test_a_rotated_key_drops_the_cache_and_refetches_once(self):
        # The cache still holds key-1; the provider now signs with key-2.
        client = _http_returning({"keys": [JWK_1, JWK_2]})
        with patch.object(id_token_module, "RedisUtils") as redis, \
             patch.object(id_token_module, "_http", return_value=client):
            redis.get_redis = AsyncMock(return_value=json.dumps(JWKS))
            redis.set_redis = AsyncMock()
            redis.delete = AsyncMock()
            cache = JwksCache("https://issuer.example/keys", "oauth:jwks:test")
            claims = await verify_id_token(_token(key=KEY_2, kid="key-2"), cache,
                                           audience=AUDIENCE, issuer=ISSUER, access_token=None)

        assert claims["sub"] == "uid-1"
        redis.delete.assert_awaited_once_with("oauth:jwks:test")
        client.get.assert_awaited_once()

    async def test_a_kid_still_missing_after_the_refetch_is_refused(self):
        client = _http_returning(JWKS)
        with patch.object(id_token_module, "RedisUtils") as redis, \
             patch.object(id_token_module, "_http", return_value=client):
            redis.get_redis = AsyncMock(return_value=json.dumps(JWKS))
            redis.set_redis = AsyncMock()
            redis.delete = AsyncMock()
            cache = JwksCache("https://issuer.example/keys", "oauth:jwks:test")
            with pytest.raises(SigningKeyNotFound):
                await verify_id_token(_token(key=KEY_2, kid="key-2"), cache,
                                      audience=AUDIENCE, issuer=ISSUER, access_token=None)

    async def test_the_retry_still_checks_the_at_hash(self):
        # The retry checks everything the first try does — the access token included.
        client = _http_returning({"keys": [JWK_1, JWK_2]})
        token = _token(key=KEY_2, kid="key-2", at_hash=_at_hash("access-1"))
        with patch.object(id_token_module, "RedisUtils") as redis, \
             patch.object(id_token_module, "_http", return_value=client):
            redis.get_redis = AsyncMock(return_value=json.dumps(JWKS))
            redis.set_redis = AsyncMock()
            redis.delete = AsyncMock()
            cache = JwksCache("https://issuer.example/keys", "oauth:jwks:test")
            with pytest.raises(jwt.InvalidTokenError, match="at_hash"):
                await verify_id_token(token, cache, audience=AUDIENCE, issuer=ISSUER, access_token="access-2")
