"""A failure inside a DB session surfaces as itself.

The session wrapper used to stringify every failure into a new exception's *message* — "Exception
during DB session usage: <the SQL, its parameters, the host error>" — which is exactly the text
that must never reach a client, and it relabelled a database outage as a 400. It now logs the
failure and re-raises the original, so the global handler can answer with a safe 500.
"""
import pytest

from main.appodus_utils.db import session as db_session


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_session_factory(monkeypatch):
    monkeypatch.setattr(db_session, "IS_SERVERLESS", False)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", lambda: _FakeSession())


class DatabaseUnreachable(Exception):
    pass


async def test_re_raises_the_original_failure(fake_session_factory):
    failure = DatabaseUnreachable("[WinError 1225] The remote computer refused the network connection")

    with pytest.raises(DatabaseUnreachable) as raised:
        async with db_session.create_new_db_session():
            raise failure

    assert raised.value is failure


async def test_does_not_turn_the_failure_into_a_user_facing_message(fake_session_factory):
    with pytest.raises(Exception) as raised:
        async with db_session.create_new_db_session():
            raise DatabaseUnreachable("[SQL: INSERT INTO users ...]")

    assert "DB session usage" not in str(raised.value)
