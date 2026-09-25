"""IdempotencyService (PRD §4.6): exactly-once creates and webhook dedup.

Keys are unique per scope among live rows (migration 0018). Reserving is one
`INSERT … ON CONFLICT DO NOTHING`, so a concurrent duplicate replays the winner instead of
failing on the constraint. An expired key is retired (soft-deleted) first, which frees its
value. Repo mocked, no DB.
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.core.idempotency.models import IdempotencyStatus
from main.app.core.idempotency.repo import IdempotencyKeyRepo
from main.app.core.idempotency.service import IdempotencyService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceConflictException, ResourceNotFoundException


@pytest.fixture(autouse=True)
def session():
    s = MagicMock()
    s.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    s.begin = _begin
    s.flush = AsyncMock()
    s.statements = []

    async def _execute(stmt):
        s.statements.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    s.execute = AsyncMock(side_effect=_execute)
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


_SCOPE = "verification.create"


def _idempotency(existing=None, created=True):
    repo = MagicMock()
    repo.retire_expired = AsyncMock()
    repo.get_by_key = AsyncMock(return_value=existing)
    repo.insert_or_get = AsyncMock(return_value=(existing or SimpleNamespace(id="new"), created))
    repo.update_return_model = AsyncMock()
    svc = object.__new__(IdempotencyService)
    svc._idempotency_repo = repo
    return svc


def _row(**over):
    base = dict(id="idem-1", key="k-1", scope=_SCOPE, status=IdempotencyStatus.COMPLETED.value,
                request_hash=None, resource_id="res-1", response_snapshot=None,
                expires_at=Utils.datetime_now() + timedelta(hours=1))
    base.update(over)
    return SimpleNamespace(**base)


class TestBeginOrReplay:
    async def test_a_fresh_key_is_reserved_in_one_statement(self):
        svc = _idempotency(created=True)

        outcome = await svc.begin_or_replay("k-1", _SCOPE, request_hash="h1")

        assert outcome.is_replay is False
        [values] = svc._idempotency_repo.insert_or_get.await_args.args
        assert svc._idempotency_repo.insert_or_get.await_args.kwargs == {"unique_index": "uq_idempotency_scope_key"}
        assert (values["key"], values["scope"], values["status"]) == ("k-1", _SCOPE, IdempotencyStatus.PENDING)
        # An expired reservation is retired first, so its key is free again.
        svc._idempotency_repo.retire_expired.assert_awaited_once_with("k-1", _SCOPE)

    async def test_a_concurrent_duplicate_replays_the_winner(self):
        winner = _row(resource_id="ver-99", response_snapshot={"vid": "VP-1"})
        svc = _idempotency(existing=winner, created=False)

        outcome = await svc.begin_or_replay("k-1", _SCOPE)

        assert (outcome.is_replay, outcome.resource_id, outcome.response_snapshot) == (True, "ver-99", {"vid": "VP-1"})

    async def test_a_reused_key_with_a_different_payload_conflicts(self):
        svc = _idempotency(existing=_row(request_hash="h1"), created=False)
        with pytest.raises(ResourceConflictException):
            await svc.begin_or_replay("k-1", _SCOPE, request_hash="DIFFERENT")



class TestComplete:
    async def test_completes_the_key_in_its_scope(self):
        svc = _idempotency(existing=_row(status=IdempotencyStatus.PENDING.value, resource_id=None))

        await svc.complete("k-1", _SCOPE, resource_id="ver-99", response_snapshot={"vid": "VP-1"})

        svc._idempotency_repo.get_by_key.assert_awaited_once_with("k-1", _SCOPE)
        update = svc._idempotency_repo.update_return_model.await_args.args[1]
        assert (update.status, update.resource_id) == (IdempotencyStatus.COMPLETED, "ver-99")

    async def test_an_unknown_key_raises(self):
        with pytest.raises(ResourceNotFoundException):
            await _idempotency(existing=None).complete("ghost", _SCOPE)


class TestClaim:
    async def test_the_first_delivery_claims(self):
        svc = _idempotency(created=True)
        assert await svc.claim("evt_1", "webhook.flutterwave") is True
        [values] = svc._idempotency_repo.insert_or_get.await_args.args
        assert values["status"] == IdempotencyStatus.COMPLETED

    async def test_a_redelivery_is_dropped(self):
        svc = _idempotency(existing=_row(key="evt_1"), created=False)
        assert await svc.claim("evt_1", "webhook.flutterwave") is False


async def test_the_key_lookup_is_scoped(session):
    await object.__new__(IdempotencyKeyRepo).get_by_key("k-1", _SCOPE)
    sql = _sql(session.statements[0])
    assert "idempotency_keys.key = %(key_1)s" in sql and "idempotency_keys.scope = %(scope_1)s" in sql


async def test_an_expired_key_is_retired_with_a_statement(session):
    await object.__new__(IdempotencyKeyRepo).retire_expired("k-1", _SCOPE)
    sql = _sql(session.statements[0])
    assert sql.startswith("UPDATE idempotency_keys SET")
    assert "deleted=%(deleted)s" in sql
    assert "idempotency_keys.expires_at <= %(expires_at_1)s" in sql and "idempotency_keys.deleted IS false" in sql


