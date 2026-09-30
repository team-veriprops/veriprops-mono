"""A stand-in DB session for service unit tests.

Every service method runs under `@transactional`, which opens a transaction on the session in
`db_session_ctx`. This fixture puts a mock there — never in a transaction, with a no-op
`begin` and `flush` — so a service can be called directly with its repos faked.

A test module opts in by importing it::

    from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)
