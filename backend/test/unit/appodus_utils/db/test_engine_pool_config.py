"""The pooled engines' limits come from the environment.

A request holds its pooled connection until it finishes. Writes that must commit on their own
(`INDEPENDENT`) take theirs from a second, separate pool, so they never wait on the pool their
caller is holding. When concurrency still outgrows a pool, requests queue for `DB_POOL_TIMEOUT`
seconds and then fail together. The sizes, overflows and wait are settings so an environment can
size them to its load, and `DB_ENABLE_LOG_POOL` logs checkouts and returns so pool pressure can be
seen rather than inferred from timeouts.
"""
import pytest

from main.appodus_utils.db import session as db_session

_POOL_ENV_KEYS = (
    "DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT", "DB_ENABLE_LOG_POOL",
    "DB_INDEPENDENT_POOL_SIZE", "DB_INDEPENDENT_MAX_OVERFLOW",
)


@pytest.fixture
def pooled(monkeypatch):
    monkeypatch.setattr(db_session, "IS_SERVERLESS", False)
    for key in _POOL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


async def _pool_of(engine):
    try:
        return engine.sync_engine.pool
    finally:
        await engine.dispose()


async def test_defaults_when_nothing_is_configured(pooled):
    pool = await _pool_of(db_session.create_db_engine_for_env())

    assert pool.size() == db_session.DEFAULT_POOL_SIZE
    assert pool._max_overflow == db_session.DEFAULT_MAX_OVERFLOW
    assert pool._timeout == db_session.DEFAULT_POOL_TIMEOUT_SECONDS
    assert not pool.echo


async def test_limits_and_pool_logging_follow_the_environment(pooled, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "20")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "4")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "7")
    monkeypatch.setenv("DB_ENABLE_LOG_POOL", "true")

    pool = await _pool_of(db_session.create_db_engine_for_env())

    assert pool.size() == 20
    assert pool._max_overflow == 4
    assert pool._timeout == 7
    assert pool.echo


def test_a_malformed_limit_fails_loudly_naming_the_key(pooled, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "lots")

    with pytest.raises(ValueError, match="DB_POOL_SIZE"):
        db_session.create_db_engine_for_env()


async def test_the_independent_pool_has_its_own_limits(pooled, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "20")
    monkeypatch.setenv("DB_INDEPENDENT_POOL_SIZE", "3")
    monkeypatch.setenv("DB_INDEPENDENT_MAX_OVERFLOW", "2")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "7")

    pool = await _pool_of(db_session.create_db_engine_for_env(independent=True))

    assert pool.size() == 3
    assert pool._max_overflow == 2
    assert pool._timeout == 7


async def test_the_independent_pool_defaults(pooled):
    pool = await _pool_of(db_session.create_db_engine_for_env(independent=True))

    assert pool.size() == db_session.DEFAULT_INDEPENDENT_POOL_SIZE
    assert pool._max_overflow == db_session.DEFAULT_INDEPENDENT_MAX_OVERFLOW
