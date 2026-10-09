"""OpenID Connect ID-token verification, shared by Google and Apple sign-in (S6 — R2.3).

A provider signs its ID tokens with one of the keys it publishes as a JSON Web Key Set. To
trust a token:

- the key is chosen by the token's `kid` from that set, and the algorithm is pinned to RS256
  (the token's own header never selects it);
- the signature, expiry, audience (our client id) and issuer must all hold;
- an `at_hash` claim must match the access token issued alongside it (OIDC Core §3.2.2.9),
  binding the two tokens together.

The key set is cached. A `kid` the cached set doesn't hold means the provider rotated its keys,
so the cache is dropped and the set fetched once more before the token is refused.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import timedelta
from typing import Optional, Sequence, Union

import jwt
from httpx import AsyncClient
from kink import di

from main.app.config.settings import settings
from main.appodus_utils.db.redis_utils import RedisUtils

ID_TOKEN_ALGORITHM = "RS256"


class SigningKeyNotFound(jwt.InvalidTokenError):
    """The token names a key (`kid`) the provider's key set doesn't hold."""


def _http() -> AsyncClient:
    return di[AsyncClient]


class JwksCache:
    """One provider's published key set, cached for `OAUTH_JWKS_CACHE_SECONDS`."""

    def __init__(self, url: str, cache_key: str):
        self.url = url
        self.cache_key = cache_key

    async def get(self) -> dict:
        raw = await RedisUtils.get_redis(self.cache_key)
        if raw:
            return json.loads(raw)
        return await self.fetch()

    async def fetch(self) -> dict:
        response = await _http().get(self.url)
        response.raise_for_status()
        jwks = response.json()
        await RedisUtils.set_redis(
            self.cache_key, json.dumps(jwks),
            time_to_live=timedelta(seconds=settings.OAUTH_JWKS_CACHE_SECONDS),
        )
        return jwks

    async def refresh(self) -> dict:
        await RedisUtils.delete(self.cache_key)
        return await self.fetch()


def _at_hash(access_token: str) -> str:
    """The left half of the access token's SHA-256, base64url without padding (RS256)."""
    digest = hashlib.sha256(access_token.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest[: len(digest) // 2]).rstrip(b"=").decode("ascii")


def _check_at_hash(claims: dict, access_token: Optional[str]) -> None:
    expected = claims.get("at_hash")
    if expected is None:
        return
    if not access_token:
        raise jwt.InvalidTokenError("The token carries an at_hash but no access token came with it.")
    if not hmac.compare_digest(_at_hash(access_token), str(expected)):
        raise jwt.InvalidTokenError("The token's at_hash does not match its access token.")


def decode_id_token(
    id_token: str, jwks: dict, *, audience: str, issuer: Union[str, Sequence[str]],
    access_token: Optional[str],
) -> dict:
    """The verified claims of *id_token*, or `jwt.InvalidTokenError` (`SigningKeyNotFound`
    when its `kid` is not in *jwks*)."""
    kid = str(jwt.get_unverified_header(id_token).get("kid") or "")
    try:
        key = jwt.PyJWKSet.from_dict(jwks)[kid]
    except KeyError as exc:
        raise SigningKeyNotFound(f"No published key has kid {kid!r}.") from exc
    claims = jwt.decode(
        id_token, key=key, algorithms=[ID_TOKEN_ALGORITHM], audience=audience,
        issuer=issuer if isinstance(issuer, str) else list(issuer),
    )
    _check_at_hash(claims, access_token)
    return claims


async def verify_id_token(
    id_token: str, keys: JwksCache, *, audience: str, issuer: Union[str, Sequence[str]],
    access_token: Optional[str],
) -> dict:
    """`decode_id_token` against the cached key set, refetched once if the provider rotated it."""
    try:
        return decode_id_token(id_token, await keys.get(), audience=audience, issuer=issuer,
                               access_token=access_token)
    except SigningKeyNotFound:
        return decode_id_token(id_token, await keys.refresh(), audience=audience, issuer=issuer,
                               access_token=access_token)
