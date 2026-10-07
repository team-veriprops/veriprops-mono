"""UserRepo's broadcast recipient queries (§18.1): one keyset page at a time, filtered in SQL.

The fan-out never loads the whole user table: each page is the next `limit` live users after the
last id it sent, in id order, so a page is the same set however many times it is asked for and
a user who signs up mid-send simply lands on a later page. The audience filter (user type or
persona) runs in the database, never over rows in Python.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.repo import UserRepo
from main.appodus_utils.db.session import db_session_ctx
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)

_AFTER = str(uuid.UUID(int=7))


def _session(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    result.scalar_one.return_value = 3
    db_session_ctx.get().execute = AsyncMock(return_value=result)


def _sql() -> str:
    stmt = db_session_ctx.get().execute.await_args.args[0]
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


async def test_a_page_is_the_next_live_ids_in_order_as_user_id_strings():
    first, second = uuid.UUID(int=8), uuid.UUID(int=9)
    _session([first, second])

    ids = await UserRepo(db=None).list_recipient_ids_page(_AFTER, 2)

    assert ids == [str(first), str(second)]  # the 36-char form notifications key on
    sql = _sql()
    assert "users.deleted IS false" in sql
    assert "users.id > %(id_1)s" in sql
    assert "ORDER BY users.id" in sql and "LIMIT %(param_1)s" in sql


async def test_the_first_page_starts_from_the_beginning():
    _session([])
    await UserRepo(db=None).list_recipient_ids_page(None, 10)
    assert "users.id >" not in _sql()


async def test_a_user_type_audience_is_filtered_in_sql():
    _session([])
    await UserRepo(db=None).list_recipient_ids_page(None, 10, user_type=UserType.ADMIN)
    assert "users.user_type = %(user_type_1)s" in _sql()


async def test_a_persona_audience_is_a_jsonb_containment():
    _session([])
    await UserRepo(db=None).list_recipient_ids_page(None, 10, persona=UserPersona.AGENT)
    assert "users.personas @> %(param_1)s::JSONB" in _sql()


async def test_the_count_uses_the_same_filter():
    _session([])
    count = await UserRepo(db=None).count_recipients(persona=UserPersona.CUSTOMER)
    assert count == 3
    sql = _sql()
    assert sql.startswith("SELECT count(users.id)")
    assert "users.personas @> %(param_1)s::JSONB" in sql and "users.deleted IS false" in sql
