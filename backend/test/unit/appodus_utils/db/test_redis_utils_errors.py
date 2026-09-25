"""`RedisUtils` failures are logged with their traceback, and a caller can refuse to carry on.

Best-effort callers (caches, provider stats) keep the old contract: the failure is logged and
they get None. A caller whose correctness depends on the store — the revoked-token check, the
revocation itself, the OAuth state — passes `strict=True` and gets the exception, so a store
outage can never quietly read as "not revoked" or "revoked".
"""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db import redis_utils
from main.appodus_utils.db.redis_utils import RedisUtils


class _Down(Exception):
    pass


@pytest.fixture
def broken_store(monkeypatch):
    client = MagicMock()
    for method in ("get", "setex", "delete", "getdel", "scan"):
        setattr(client, method, AsyncMock(side_effect=_Down("connection refused")))
    monkeypatch.setattr(redis_utils, "redis", client)
    fake_logger = MagicMock()
    monkeypatch.setattr(redis_utils, "logger", fake_logger)
    return fake_logger


CALLS = [
    pytest.param(lambda **kw: RedisUtils.get_redis("k", **kw), id="get"),
    pytest.param(lambda **kw: RedisUtils.set_redis("k", "v", timedelta(seconds=5), **kw), id="set"),
    pytest.param(lambda **kw: RedisUtils.delete("k", **kw), id="delete"),
    pytest.param(lambda **kw: RedisUtils.pop("k", **kw), id="pop"),
    pytest.param(lambda **kw: RedisUtils.delete_by_prefix("k", **kw), id="delete_by_prefix"),
]


@pytest.mark.parametrize("call", CALLS)
async def test_best_effort_logs_the_failure_and_carries_on(broken_store, call, capsys):
    result = await call()

    assert result in (None, 0)
    broken_store.exception.assert_called_once()
    # Never printed to stdout, where no log shipper sees it.
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("call", CALLS)
async def test_strict_logs_then_raises(broken_store, call):
    with pytest.raises(_Down):
        await call(strict=True)

    broken_store.exception.assert_called_once()


async def test_the_sql_fallback_is_strict_too(monkeypatch):
    monkeypatch.setattr(redis_utils, "redis", None)
    store = MagicMock()
    store.get = AsyncMock(side_effect=_Down("db down"))
    monkeypatch.setattr(redis_utils, "key_value_service", store)
    monkeypatch.setattr(redis_utils, "logger", MagicMock())

    with pytest.raises(_Down):
        await RedisUtils.get_redis("k", strict=True)
    assert await RedisUtils.get_redis("k") is None
