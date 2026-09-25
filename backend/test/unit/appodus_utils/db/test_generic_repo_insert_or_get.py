"""`GenericRepo.insert_or_get`: get-or-create that can't race into a unique constraint.

Selecting and then inserting lets two concurrent requests both see "absent", and both insert.
The second insert then violates the unique constraint and becomes a 500. A single
`INSERT … ON CONFLICT DO NOTHING RETURNING` waits for the other transaction and then either
inserts or yields. When it yields, the row that won is read back.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsent
from main.appodus_utils.db.models import Object
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import db_session_ctx


class _Dto(Object):
    user_id: str


@pytest.fixture
def captured():
    state = {"statements": [], "results": []}

    async def _execute(stmt):
        state["statements"].append(stmt)
        result = MagicMock()
        value = state["results"].pop(0) if state["results"] else None
        result.scalar_one_or_none.return_value = value
        result.scalars.return_value.first.return_value = value
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)
    token = db_session_ctx.set(session)
    yield state
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


def _repo() -> GenericRepo:
    return GenericRepo(db=None, model=WhatsAppConsent, query_qto=_Dto)


async def test_a_fresh_row_is_inserted_in_one_statement(captured):
    fresh = WhatsAppConsent(user_id="u1")
    captured["results"] = [fresh]

    row, created = await _repo().insert_or_get({"user_id": "u1"}, ["user_id"])

    assert (row, created) == (fresh, True)
    [stmt] = captured["statements"]
    sql = _sql(stmt)
    assert sql.startswith("INSERT INTO whatsapp_consents")
    assert "ON CONFLICT (user_id) DO NOTHING RETURNING" in sql
    # The base columns a plain create would set are set here too.
    params = stmt.compile(dialect=postgresql.dialect()).params
    assert params["user_id"] == "u1" and params["version"] == 1 and params["deleted"] is False
    assert params["id"] is not None and params["date_created"] is not None


async def test_on_conflict_the_winning_row_is_returned(captured):
    winner = WhatsAppConsent(user_id="u1")
    captured["results"] = [None, winner]

    row, created = await _repo().insert_or_get({"user_id": "u1"}, ["user_id"])

    assert (row, created) == (winner, False)
    reread = _sql(captured["statements"][1])
    assert reread.startswith("SELECT") and "WHERE whatsapp_consents.user_id = %(user_id_1)s" in reread


async def test_a_partial_unique_index_is_targeted_by_name(captured):
    """The conflict target is read off the model's index, so it matches the index Postgres has.

    A hand-written predicate that merely means the same (`deleted IS false` for an index
    on `deleted = false`) is rejected by Postgres: it must prove the predicates match.
    """
    from main.app.domain.user.auth.signup_draft.models import SignupDraft

    repo = GenericRepo(db=None, model=SignupDraft, query_qto=_Dto)
    captured["results"] = [None, object()]

    await repo.insert_or_get({"email": "a@example.com"}, unique_index="uq_signup_drafts_email")

    insert_sql = _sql(captured["statements"][0])
    assert "ON CONFLICT (email) WHERE deleted = false DO NOTHING" in insert_sql
    reread = _sql(captured["statements"][1])
    assert "signup_drafts.email = %(email_1)s" in reread and "deleted = false" in reread


def test_an_unknown_index_name_fails_loudly():
    with pytest.raises(ValueError, match="uq_nope"):
        _repo()._unique_index_target("uq_nope")
