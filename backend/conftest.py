"""Root pytest conftest — bootstraps the environment so domain modules can
import without ValueError on unset env vars. The env file is selected via
`APPODUS_ACTIVE_ENV` (default 'test')."""
import os

# Default to the inert test env (.env.test: throwaway localhost DB, scheduler
# off, all stubs on, zero secrets) so a plain `pytest` runs under the test-env
# policy. Export APPODUS_ACTIVE_ENV explicitly to target another env file.
os.environ.setdefault("APPODUS_ACTIVE_ENV", "test")

# Importing the settings module triggers `set_env_vars()` which populates
# os.environ from `.env.{APPODUS_ACTIVE_ENV}` — required before any module
# that reads env vars at import time (logger, db.session, etc.).
from main.app.config import settings as _settings  # noqa: F401, E402
from main.app.config.bootstrap import DiBootstrap  # noqa: F401, E402

import pytest  # noqa: E402


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
