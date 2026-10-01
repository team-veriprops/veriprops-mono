"""CallbackRepo's unhandled-event lookups run on the async session.

A webhook handler asks "have we already recorded this provider event?" before storing it.
The lookup used the sync ORM's `session.query`, which `AsyncSession` does not have, so every
such check raised AttributeError. These tests pin that both lookups issue an awaited
`select` scoped to live, unhandled rows for the exact platform/event/external-id triple.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql import Select

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.domain.webhook.callback.model import Callback, CallbackType
from main.appodus_utils.domain.webhook.callback.repo import CallbackRepo

EVENT = dict(
    platform=IntegratedPlatform.GOOGLE_DRIVE,
    event_type=CallbackType.CONTRACT_SIGNED,
    external_id="ext-1",
)


@pytest.fixture
def session():
    session = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _repo() -> CallbackRepo:
    repo = object.__new__(CallbackRepo)
    repo._model = Callback
    repo._db_utils = MagicMock()
    return repo


def _where_sql(stmt: Select) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()


@pytest.mark.parametrize("found, expected", [(True, True), (None, False)])
async def test_exists_is_an_awaited_select_for_the_unhandled_event(session, found, expected):
    result = MagicMock()
    result.scalar.return_value = found
    session.execute = AsyncMock(return_value=result)

    assert await _repo().exists_by_platform_event_type_and_external_id(**EVENT) is expected

    stmt = session.execute.await_args.args[0]
    assert isinstance(stmt, Select)
    sql = _where_sql(stmt)
    for predicate in (
        "callbacks.deleted is false",
        "callbacks.handled is false",
        "callbacks.platform = 'google_drive'",
        "callbacks.event_type = 'contract_signed'",
        "callbacks.external_id = 'ext-1'",
    ):
        assert predicate in sql, predicate


async def test_get_returns_the_matching_row_as_its_query_dto(session):
    row = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result)
    repo = _repo()
    repo._db_utils.build_row_response.return_value = "dto"

    assert await repo.get_by_platform_event_type_and_external_id(**EVENT) == "dto"
    repo._db_utils.build_row_response.assert_called_once_with(row=row, return_success_response_obj=False)


async def test_get_without_a_match_is_none(session):
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result)

    assert await _repo().get_by_platform_event_type_and_external_id(**EVENT) is None
