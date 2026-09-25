"""`RedisUtils` counters and single-use reads are atomic on both backends.

- Redis: `INCR` and `EXPIRE … NX` run in one transaction pipeline. A separate `EXPIRE` that never
  ran used to leave a counter with no TTL, which blocked that IP/scope forever.
- SQL fallback: one atomic statement with a fixed window, matching Redis. It used to read,
  increment and write back, with an expiry that moved on every hit.
- `pop` hands a value to exactly one caller (`GETDEL` / `DELETE … RETURNING`).
"""
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from main.appodus_utils.db import redis_utils
from main.appodus_utils.db.redis_utils import RedisUtils


class _FakePipeline:
    def __init__(self, calls, results):
        self._calls = calls
        self._results = results

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def incr(self, key):
        self._calls.append(("incr", key))
        return self

    def expire(self, key, seconds, nx=False):
        self._calls.append(("expire", key, seconds, nx))
        return self

    async def execute(self):
        return self._results


class _FakeRedis:
    def __init__(self, results=(1, True), popped=None):
        self.calls = []
        self.transactions = []
        self._results = list(results)
        self._popped = popped

    def pipeline(self, transaction=True):
        self.transactions.append(transaction)
        return _FakePipeline(self.calls, self._results)

    async def getdel(self, key):
        self.calls.append(("getdel", key))
        return self._popped


async def test_redis_counter_sets_its_ttl_in_the_same_transaction(monkeypatch):
    fake = _FakeRedis(results=(4, False))
    monkeypatch.setattr(redis_utils, "redis", fake)

    count = await RedisUtils.incr_with_ttl("ratelimit:login:1.2.3.4", 60)

    assert count == 4
    assert fake.transactions == [True]
    assert fake.calls == [
        ("incr", "ratelimit:login:1.2.3.4"),
        ("expire", "ratelimit:login:1.2.3.4", 60, True),
    ]


async def test_sql_counter_is_one_atomic_fixed_window_increment(monkeypatch):
    kv = AsyncMock()
    kv.incr = AsyncMock(return_value=2)
    monkeypatch.setattr(redis_utils, "redis", {})
    monkeypatch.setattr(redis_utils, "key_value_service", kv)

    count = await RedisUtils.incr_with_ttl("ratelimit:login:1.2.3.4", 60)

    assert count == 2
    kv.incr.assert_awaited_once_with("ratelimit:login:1.2.3.4", timedelta(seconds=60), sliding=False)
    kv.get.assert_not_called()
    kv.set.assert_not_called()


async def test_a_counter_failure_still_fails_open(monkeypatch):
    kv = AsyncMock()
    kv.incr = AsyncMock(side_effect=RuntimeError("store down"))
    monkeypatch.setattr(redis_utils, "redis", {})
    monkeypatch.setattr(redis_utils, "key_value_service", kv)

    assert await RedisUtils.incr_with_ttl("ratelimit:login:1.2.3.4", 60) == 0


@pytest.mark.parametrize("stored, expected", [(b"state-json", "state-json"), (None, None)])
async def test_redis_pop_uses_getdel(monkeypatch, stored, expected):
    fake = _FakeRedis(popped=stored)
    monkeypatch.setattr(redis_utils, "redis", fake)

    assert await RedisUtils.pop("oauth:state:s") == expected
    assert fake.calls == [("getdel", "oauth:state:s")]


async def test_sql_pop_uses_the_atomic_store_pop(monkeypatch):
    kv = AsyncMock()
    kv.pop = AsyncMock(return_value="state-json")
    monkeypatch.setattr(redis_utils, "redis", {})
    monkeypatch.setattr(redis_utils, "key_value_service", kv)

    assert await RedisUtils.pop("oauth:state:s") == "state-json"
    kv.pop.assert_awaited_once_with("oauth:state:s")
