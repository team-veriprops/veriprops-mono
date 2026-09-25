"""Writes that must commit on their own, without waiting on the caller's connection.

Some writes have to survive the caller's failure: an OTP failure count when the guess is then
rejected, the record of a message already handed to a provider, a turn claim that must be visible
before a slow model call. `INDEPENDENT` gives each its own transaction, drawn from a separate pool.
Drawing it from the request's pool is what starved that pool under load: every request held one
connection while waiting for a second.
"""
from contextlib import asynccontextmanager

import pytest

from main.appodus_utils.db import session as db_session
from main.appodus_utils.decorators import audit_ctx
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional


class _FakeSession:
    """Records how its transaction ended."""

    def __init__(self, pool: str):
        self.pool = pool
        self.info: dict = {}
        self.outcome = None
        self._in_tx = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def in_transaction(self) -> bool:
        return self._in_tx

    def begin(self):
        session = self

        @asynccontextmanager
        async def _tx():
            session._in_tx = True
            try:
                yield
            except BaseException:
                session.outcome = "rollback"
                raise
            else:
                session.outcome = "commit"
            finally:
                session._in_tx = False

        return _tx()

    async def flush(self):
        pass


@pytest.fixture
def pools(monkeypatch):
    opened: list[_FakeSession] = []

    def _factory(pool):
        def _make():
            s = _FakeSession(pool)
            opened.append(s)
            return s
        return _make

    monkeypatch.setattr(db_session, "IS_SERVERLESS", False)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", _factory("main"))
    monkeypatch.setattr(db_session, "IndependentSessionLocal", _factory("independent"))
    return opened


@pytest.fixture
def request_session():
    """The session a request (or job) holds in context while it calls an independent write."""
    s = _FakeSession("main")
    token = db_session.set_db_session_context(s)
    yield s
    db_session.db_session_ctx.reset(token)


@transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
async def _independent_write():
    return db_session.get_db_session_from_context()


@transactional(session_policy=TransactionSessionPolicy.INDEPENDENT)
async def _independent_write_calling_another():
    outer = db_session.get_db_session_from_context()
    inner = await _independent_write()
    return outer, inner


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _top_level_unit():
    return db_session.get_db_session_from_context()


async def test_uses_the_independent_pool_not_the_callers(pools, request_session):
    used = await _independent_write()

    assert used.pool == "independent"
    assert used is not request_session
    assert db_session.is_independent_session(used)


async def test_commits_even_when_the_caller_then_fails(pools, request_session):
    @transactional()
    async def _caller():
        await _independent_write()
        raise RuntimeError("the request fails after the write")

    with pytest.raises(RuntimeError):
        await _caller()

    independent = [s for s in pools if s.pool == "independent"]
    assert [s.outcome for s in independent] == ["commit"]
    assert request_session.outcome == "rollback"


async def test_a_nested_independent_write_joins_its_independent_parent(pools, request_session):
    outer, inner = await _independent_write_calling_another()

    assert inner is outer
    assert [s.pool for s in pools] == ["independent"]


async def test_works_with_no_session_in_context(pools):
    used = await _independent_write()

    assert used.pool == "independent"


async def test_always_new_stays_on_the_main_pool(pools):
    used = await _top_level_unit()

    assert used.pool == "main"
    assert not db_session.is_independent_session(used)


async def test_a_mock_session_is_not_mistaken_for_an_independent_one():
    from unittest.mock import MagicMock

    assert not db_session.is_independent_session(MagicMock())


async def test_a_nested_transaction_keeps_the_callers_queued_audit_writes(pools, request_session):
    """The caller's queued audit rows must still be written when a nested transaction opens.

    Opening the nested transaction used to reset the audit queue in the caller's own context,
    silently dropping every audit row the caller had queued before that call.
    """
    written = []

    @transactional()
    async def _caller():
        audit_ctx.schedule_audit_write(lambda: _record(written, "caller-before"))
        await _independent_write()
        audit_ctx.schedule_audit_write(lambda: _record(written, "caller-after"))

    await _caller()

    assert written == ["caller-before", "caller-after"]


async def _record(sink, name):
    sink.append(name)
