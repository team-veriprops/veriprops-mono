"""Root pytest conftest — bootstraps the environment so domain modules can
import without ValueError on unset env vars. The env file is selected via
`APPODUS_ACTIVE_ENV` (default 'test')."""
import os

# Default to the inert test env (.env.test: throwaway localhost DB, scheduler
# off, all stubs on, zero secrets) so a plain `pytest` runs under the test-env
# policy. Export APPODUS_ACTIVE_ENV explicitly to target another env file.
os.environ.setdefault("APPODUS_ACTIVE_ENV", "test")
# Committed env files keep the JWT key a placeholder (test_env_hygiene.py), and `CHANGE_ME` is
# too short for HS256 — PyJWT warns on every token. Unit tests sign with a full-length key that
# is a test fixture, not a secret; the process env wins over the env file, as Doppler's does.
os.environ.setdefault("AUTHJWT_SECRET_KEY", "unit-tests-only-hs256-signing-key-not-a-secret")

# Importing the settings module triggers `set_env_vars()` which populates
# os.environ from `.env.{APPODUS_ACTIVE_ENV}` — required before any module
# that reads env vars at import time (logger, db.session, etc.).
from main.app.config import settings as _settings  # noqa: F401, E402
from main.app.config.bootstrap import DiBootstrap  # noqa: F401, E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def subscriber_faults(request, monkeypatch):
    """Fail a test whose event bus quietly swallowed a subscriber failure.

    The bus is best-effort by design (§4.8): a failing subscriber is logged and the publisher
    carries on, so a service test that reaches the real subscribers through a mock session
    passes while every notification it publishes crashes. A test that means to exercise a
    failing subscriber says so with `@pytest.mark.subscriber_faults_expected` and can read
    the faults from this fixture.
    """
    from main.app.core.events import bus as bus_module

    faults = []
    original = bus_module.log_fault_once

    def _record(exc, where, **kwargs):
        faults.append((exc, where))
        return original(exc, where, **kwargs)

    monkeypatch.setattr(bus_module, "log_fault_once", _record)
    yield faults
    if faults and request.node.get_closest_marker("subscriber_faults_expected") is None:
        listed = "\n".join(f"  {where}: {exc!r}" for exc, where in faults)
        pytest.fail(
            "The event bus swallowed subscriber failures in this test. Stub "
            "`publish_domain_event` for a service test, or mark the test "
            f"`subscriber_faults_expected`:\n{listed}",
            pytrace=False,
        )


@pytest.fixture
def published_events(monkeypatch):
    """Swap the app's event bus for one whose only subscriber records what is published.

    A service unit test asserts on what the service *announces*, not on what the
    notification, SSE and chat subscribers then do with it (those have their own tests), and
    the real subscribers cannot run against a mock session anyway.
    """
    from main.app.core.events.bus import EventBus
    from test.utils.di_override import override_service

    published = []
    bus = EventBus()

    async def _record(event):
        published.append(event)

    bus.subscribe(_record)
    override_service(monkeypatch, EventBus, bus)
    return published


@pytest.fixture
def independent_sessions(monkeypatch):
    """Stand in for the independent-write pool (`TransactionSessionPolicy.INDEPENDENT`).

    Unit tests have no database, so a method whose writes commit on their own would find
    no session factory. Each independent session opened is a mock appended to the returned
    list, so a test can assert *where* a write happened — in its own transaction rather
    than the caller's.
    """
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    from main.appodus_utils.db import session as db_session

    opened = []

    @asynccontextmanager
    async def _begin():
        yield

    def _factory():
        s = MagicMock()
        s.info = {}
        s.in_transaction.return_value = False
        s.begin = _begin
        s.flush = AsyncMock()
        s.execute = AsyncMock()
        s.__aenter__.return_value = s
        s.__aexit__.return_value = False
        opened.append(s)
        return s

    monkeypatch.setattr(db_session, "IS_SERVERLESS", False)
    monkeypatch.setattr(db_session, "IndependentSessionLocal", _factory)
    return opened
