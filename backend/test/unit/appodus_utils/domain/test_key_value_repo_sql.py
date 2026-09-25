"""The SQL key/value store stays correct under concurrent requests.

Each operation is a single statement, so two requests touching one key can't interleave:
- a first write no longer races into the primary key (INSERT … ON CONFLICT);
- a counter no longer loses increments (read, add, write back);
- a read no longer deletes a value a concurrent write just refreshed;
- a single-use value is consumed by exactly one caller (DELETE … RETURNING).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.domain.key_value.models import UpsertKeyValue
from main.appodus_utils.domain.key_value.repo import KeyValueRepo

_NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def captured(monkeypatch):
    """Record each executed statement; `rows` queues what each execute returns."""
    state = {"statements": [], "rows": []}

    async def _execute(stmt):
        state["statements"].append(stmt)
        result = MagicMock()
        row = state["rows"].pop(0) if state["rows"] else None
        result.first.return_value = row
        result.scalar_one_or_none.return_value = row
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    token = db_session_ctx.set(session)
    monkeypatch.setattr("main.appodus_utils.domain.key_value.repo.Utils.datetime_now", lambda: _NOW)
    yield state
    db_session_ctx.reset(token)
    session.commit.assert_not_awaited()  # the transactional decorator owns the commit


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


def _row(value: bytes, expires_at: datetime):
    row = MagicMock()
    row.value = value
    row.expires_at = expires_at
    return row


async def test_upsert_is_a_single_insert_on_conflict(captured):
    await KeyValueRepo().upsert(UpsertKeyValue(key="k", value=b"v", expires_at=_NOW))

    [stmt] = captured["statements"]
    sql = _sql(stmt)
    assert sql.startswith("INSERT INTO key_values")
    assert "ON CONFLICT (key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at" in sql


async def test_get_returns_a_live_value_without_writing(captured):
    captured["rows"] = [_row(b"v", _NOW + timedelta(minutes=1))]

    got = await KeyValueRepo().get("k")

    assert got.value == b"v"
    assert len(captured["statements"]) == 1
    assert _sql(captured["statements"][0]).startswith("SELECT")


async def test_get_evicts_an_expired_value_only_if_it_is_still_expired(captured):
    captured["rows"] = [_row(b"old", _NOW - timedelta(seconds=1))]

    assert await KeyValueRepo().get("k") is None

    evict = _sql(captured["statements"][1])
    assert evict.startswith("DELETE FROM key_values")
    # The expiry predicate spares a value a concurrent write refreshed in the meantime.
    assert "key_values.key = %(key_1)s AND key_values.expires_at <= %(expires_at_1)s" in evict


@pytest.mark.parametrize("sliding", [False, True])
async def test_incr_is_one_atomic_statement(captured, sliding):
    captured["rows"] = [b"3"]

    count = await KeyValueRepo().incr("k", timedelta(seconds=60), sliding=sliding)

    assert count == 3
    [stmt] = captured["statements"]
    sql = _sql(stmt)
    assert sql.startswith("INSERT INTO key_values")
    # An expired counter restarts at the inserted 1; a live one is incremented in SQL.
    assert "ON CONFLICT (key) DO UPDATE SET value = CASE WHEN (key_values.expires_at <=" in sql
    assert "THEN excluded.value ELSE convert_to(CAST(CAST(convert_from(key_values.value," in sql
    assert "AS BIGINT) + %(param_" in sql
    assert sql.endswith("RETURNING key_values.value")
    if sliding:
        assert "expires_at = excluded.expires_at RETURNING" in sql
    else:
        # A fixed window keeps the live row's expiry.
        assert "THEN excluded.expires_at ELSE key_values.expires_at END" in sql


async def test_incr_with_a_limit_refuses_without_writing(captured):
    captured["rows"] = [None]  # the conditional DO UPDATE matched nothing

    count = await KeyValueRepo().incr("k", timedelta(seconds=60), sliding=True, limit=3)

    assert count is None
    sql = _sql(captured["statements"][0])
    # Only an expired row or one still below the limit is updated.
    assert "WHERE key_values.expires_at <=" in sql
    assert "OR CAST(convert_from(key_values.value," in sql and "AS BIGINT) < %(param_" in sql


async def test_pop_consumes_with_delete_returning(captured):
    captured["rows"] = [_row(b"123456", _NOW + timedelta(minutes=5))]

    assert await KeyValueRepo().pop("k") == b"123456"

    [stmt] = captured["statements"]
    sql = _sql(stmt)
    assert sql.startswith("DELETE FROM key_values WHERE key_values.key =")
    assert sql.endswith("RETURNING key_values.value, key_values.expires_at")


async def test_pop_of_an_expired_value_returns_nothing(captured):
    captured["rows"] = [_row(b"123456", _NOW - timedelta(seconds=1))]

    assert await KeyValueRepo().pop("k") is None


async def test_deletes_leave_the_commit_to_the_transaction(captured):
    repo = KeyValueRepo()
    await repo.delete("k")
    await repo.delete_by_prefix("otp:")
    await repo.cleanup_expired()

    assert [_sql(s).split()[0] for s in captured["statements"]] == ["DELETE"] * 3
