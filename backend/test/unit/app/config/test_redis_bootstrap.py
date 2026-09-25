"""`REDIS_ENABLED` decides which store `RedisUtils` uses.

`RedisUtils` resolves `di[redis.asyncio.Redis]` and awaits every call on it, so an enabled Redis
must be registered under that key as an asyncio client. A client registered under any other key,
or a synchronous one, silently leaves `RedisUtils` on the SQL key/value fallback.
"""
import pytest
from kink import di
from redis.asyncio import Redis as AsyncRedis

from main.app.config import bootstrap as app_bootstrap
from main.app.config.settings import settings


@pytest.fixture
def reinject_after(monkeypatch):
    yield
    monkeypatch.undo()
    app_bootstrap.di_bootstrap.inject_redis()


def test_enabled_registers_an_asyncio_client_under_the_key_redis_utils_reads(reinject_after, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "REDIS_PORT", "6390")
    monkeypatch.setattr(settings, "REDIS_DB", "2")

    app_bootstrap.di_bootstrap.inject_redis()
    client = di[AsyncRedis]

    assert isinstance(client, AsyncRedis)
    kwargs = client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("127.0.0.1", 6390, 2)


def test_disabled_leaves_redis_utils_on_the_sql_fallback(reinject_after, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_ENABLED", False)

    app_bootstrap.di_bootstrap.inject_redis()

    assert not di[AsyncRedis]
