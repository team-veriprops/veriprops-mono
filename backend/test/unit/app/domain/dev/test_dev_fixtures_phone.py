"""Fixture phone numbers are drawn free, never just probably free.

A QA number is the fixed `8100` prefix plus six random digits — a million numbers, the prefix being
what marks it as QA. The database is not reset between scenarios, so a six-engine browser run
creates thousands of fixture users, and a blind draw then collides on `uq_users_phone_e164`, which
answered `/dev/scenario` with a 500. `free_qa_local_phones` asks the database which candidates are
taken and draws again until every number is free and distinct.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from main.app.domain.dev import fixtures
from main.app.domain.dev.fixtures import free_qa_local_phones


def _session(taken: set[str]):
    session = MagicMock()

    async def _execute(stmt, params):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [p for p in params["phones"] if p in taken]
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


def _draws(monkeypatch, *numbers: str):
    sequence = iter(numbers)
    monkeypatch.setattr(fixtures, "unique_qa_local_phone", lambda: next(sequence))


async def test_numbers_already_held_are_drawn_again(monkeypatch):
    _draws(monkeypatch, "8100000001", "8100000002", "8100000003")
    phones = await free_qa_local_phones(_session(taken={"+2348100000001"}), 2)
    assert phones == ["8100000002", "8100000003"]


async def test_a_batch_never_holds_the_same_number_twice(monkeypatch):
    _draws(monkeypatch, "8100000007", "8100000007", "8100000008")
    phones = await free_qa_local_phones(_session(taken=set()), 2)
    assert phones == ["8100000007", "8100000008"]


async def test_the_check_is_one_query_per_round(monkeypatch):
    _draws(monkeypatch, "8100000001", "8100000002", "8100000003", "8100000004")
    session = _session(taken=set())
    await free_qa_local_phones(session, 4)
    assert session.execute.await_count == 1
