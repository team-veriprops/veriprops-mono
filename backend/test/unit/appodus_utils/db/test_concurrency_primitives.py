"""The shared tools for writes that must stay correct under concurrent requests.

- `GenericRepo.upsert`: create or update one row in a single statement.
- `advisory_xact_lock`: serialise writers of something no unique index can describe
  (a replace-the-whole-set write, a one-open-request rule) until the transaction ends.
- `unique_violation_as`: turn a violation of one *named* unique index into the domain error
  the caller should see, inside a savepoint so the transaction stays usable.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from main.appodus_utils.db.integrity import unique_violation_as
from main.appodus_utils.db.locks import advisory_xact_lock, try_advisory_xact_lock
from main.appodus_utils.db.models import Object
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import db_session_ctx


class _Dto(Object):
    key: str


@pytest.fixture
def session():
    s = MagicMock()
    s.statements = []
    s.savepoints = 0

    async def _execute(stmt, *args, **kwargs):
        s.statements.append(stmt)
        result = MagicMock()
        result.scalar_one.return_value = True
        return result

    @asynccontextmanager
    async def _nested():
        s.savepoints += 1
        yield

    s.execute = AsyncMock(side_effect=_execute)
    s.begin_nested = _nested
    s.flush = AsyncMock()
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


async def test_upsert_is_one_insert_on_conflict_do_update(session):
    from main.app.domain.system_config.models import SystemConfig

    repo = GenericRepo(db=None, model=SystemConfig, query_qto=_Dto)

    await repo.upsert({"key": "k", "value_json": 5}, ["value_json"], unique_index="uq_system_config_key")

    [stmt] = session.statements
    sql = _sql(stmt)
    assert sql.startswith("INSERT INTO system_config")
    assert "ON CONFLICT (key) WHERE deleted = false DO UPDATE SET value_json = excluded.value_json" in sql
    assert "version = (system_config.version + %(version_1)s)" in sql
    assert "date_updated = %(param_1)s" in sql
    assert "RETURNING" in sql
    # An instance already loaded in the session is refreshed with what was written.
    assert stmt.get_execution_options().get("populate_existing") is True


async def test_advisory_lock_is_transaction_scoped_and_keyed_by_hash(session):
    await advisory_xact_lock("trust_weights:PREMIUM")

    sql = _sql(session.statements[0])
    assert sql == "SELECT pg_advisory_xact_lock(hashtextextended(%(hashtextextended_1)s, %(hashtextextended_2)s)) AS pg_advisory_xact_lock_1"
    params = session.statements[0].compile(dialect=postgresql.dialect()).params
    assert params["hashtextextended_1"] == "trust_weights:PREMIUM"


async def test_try_lock_reports_whether_it_was_acquired(session):
    assert await try_advisory_xact_lock("job:sweep") is True
    assert "pg_try_advisory_xact_lock" in _sql(session.statements[0])


def _violation(constraint: str) -> IntegrityError:
    orig = Exception(f'duplicate key value violates unique constraint "{constraint}"')
    orig.constraint_name = constraint
    return IntegrityError("INSERT …", {}, orig)


class _Taken(Exception):
    pass


async def test_a_named_violation_becomes_the_domain_error(session):
    session.flush = AsyncMock(side_effect=_violation("uq_whatsapp_links_phone_e164"))

    with pytest.raises(_Taken):
        async with unique_violation_as("uq_whatsapp_links_phone_e164", _Taken):
            pass

    assert session.savepoints == 1


async def test_any_other_violation_is_not_disguised(session):
    session.flush = AsyncMock(side_effect=_violation("uq_whatsapp_links_user_id"))

    with pytest.raises(IntegrityError):
        async with unique_violation_as("uq_whatsapp_links_phone_e164", _Taken):
            pass


async def test_a_clean_write_is_flushed_inside_the_savepoint(session):
    async with unique_violation_as("uq_whatsapp_links_phone_e164", _Taken):
        pass

    session.flush.assert_awaited_once()
    assert session.savepoints == 1
