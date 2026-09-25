"""Serverless sessions: one NullPool engine per running event loop, never a module global.

A serverless platform may run each invocation on a fresh event loop, and an engine created on
one loop must not be used on another. Building a new engine for *every* session is the other
failure: nothing ever disposes it, and assigning it to the module globals lets a nested
session (an independent write) replace the engine the request's own session came from. So
the engine is cached per loop — the same loop reuses it, a new loop gets its own — and
opening a session never reassigns a global.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db import session as db_session


@pytest.fixture
def serverless(monkeypatch):
    """Serverless mode with engine construction counted instead of connecting anywhere."""
    built = []

    def _engine(independent: bool = False):
        engine = MagicMock(name=f"engine-{len(built)}")
        engine.dispose = AsyncMock()
        built.append(engine)
        return engine

    monkeypatch.setattr(db_session, "IS_SERVERLESS", True)
    monkeypatch.setattr(db_session, "create_db_engine_for_env", _engine)
    monkeypatch.setattr(db_session, "engine", None)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", None)
    monkeypatch.setattr(db_session, "_loop_engines", type(db_session._loop_engines)())
    return built


async def _session_binds(n: int, independent: bool = False):
    binds = []
    for _ in range(n):
        async with db_session.create_new_db_session(independent=independent) as session:
            binds.append(session.bind)
    return binds


def test_one_loop_reuses_one_engine(serverless):
    binds = asyncio.run(_session_binds(3))

    assert len(serverless) == 1
    assert binds == [serverless[0]] * 3


def test_each_loop_gets_its_own_engine(serverless):
    first = asyncio.run(_session_binds(1))
    second = asyncio.run(_session_binds(1))

    assert len(serverless) == 2
    assert first[0] is not second[0]


def test_opening_a_session_never_reassigns_the_module_globals(serverless):
    asyncio.run(_session_binds(2))
    asyncio.run(_session_binds(1, independent=True))

    assert db_session.engine is None
    assert db_session.AsyncSessionLocal is None


def test_a_nested_independent_session_leaves_the_outer_one_in_context(serverless):
    async def _nested():
        async with db_session.create_new_db_session() as outer:
            async with db_session.create_new_db_session(independent=True) as inner:
                assert db_session.is_independent_session(inner)
                assert inner.bind is outer.bind  # NullPool: a connection per session, one engine
            return outer, db_session.get_db_session_from_context()

    outer, in_context = asyncio.run(_nested())
    assert in_context is outer


def test_close_disposes_the_cached_engine(serverless):
    async def _open_then_close():
        await _session_binds(1)
        await db_session.close_db_engine()

    asyncio.run(_open_then_close())

    serverless[0].dispose.assert_awaited_once()
