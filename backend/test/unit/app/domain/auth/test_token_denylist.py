"""The revoked-token denylist fails closed, and a revocation lasts exactly as long as the token.

- A store error during the check rejects the request (the standard safe 5xx with a reference)
  instead of treating an unreadable denylist as "not revoked" and accepting a revoked token.
  The tradeoff: while the key/value store is down, authenticated requests fail.
- A revocation is written strictly, so logout can report that it did not take.
- Its lifetime is the token's remaining life (`exp - now`, at least a second). The absolute
  `exp` timestamp used to be passed as a duration — about 56 years.
"""
import time
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.utils import jwt_auth_utils
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils


@pytest.fixture
def store(monkeypatch):
    fake = MagicMock()
    fake.get_redis = AsyncMock(return_value=None)
    fake.set_redis = AsyncMock()
    monkeypatch.setattr(jwt_auth_utils, "RedisUtils", fake)
    return fake


def _authorize(exp: int):
    authorize = MagicMock()
    authorize.jwt_required = AsyncMock()
    authorize.get_raw_jwt = MagicMock(return_value={"jti": "jti-1", "exp": exp})
    return authorize


class TestDenylistCheck:
    async def test_a_revoked_token_is_rejected(self, store):
        store.get_redis = AsyncMock(return_value="true")
        assert await JwtAuthUtils.check_if_token_in_denylist({"jti": "jti-1"}) is True
        store.get_redis.assert_awaited_once_with("token_jti:jti-1", strict=True)

    async def test_an_unrevoked_token_passes(self, store):
        assert await JwtAuthUtils.check_if_token_in_denylist({"jti": "jti-1"}) is False

    async def test_a_store_error_fails_closed(self, store):
        store.get_redis = AsyncMock(side_effect=ConnectionError("store down"))
        with pytest.raises(ConnectionError):
            await JwtAuthUtils.check_if_token_in_denylist({"jti": "jti-1"})


class TestRevocation:
    async def test_it_lasts_for_the_tokens_remaining_life(self, store):
        await JwtAuthUtils.revoke_token(_authorize(exp=int(time.time()) + 600))

        key, value, ttl = store.set_redis.await_args.args
        assert (key, value) == ("token_jti:jti-1", "true")
        assert timedelta(seconds=590) <= ttl <= timedelta(seconds=600)
        assert store.set_redis.await_args.kwargs == {"strict": True}

    async def test_an_already_expired_token_is_still_stored_briefly(self, store):
        await JwtAuthUtils.revoke_token(_authorize(exp=int(time.time()) - 30))

        assert store.set_redis.await_args.args[2] == timedelta(seconds=1)

    async def test_a_failed_write_propagates(self, store):
        store.set_redis = AsyncMock(side_effect=ConnectionError("store down"))
        with pytest.raises(ConnectionError):
            await JwtAuthUtils.revoke_token(_authorize(exp=int(time.time()) + 600))
