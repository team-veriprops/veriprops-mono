"""One live membership per (conversation, user) — concurrent first opens must converge.

A thread's mark-read and the reply that follows it can reach the server together; both used
to see "not a member yet" and both inserted, doubling the member's row in the admin inbox.
The unique index makes the loser's insert fail, and `ensure_participant` then hands back the
winner's row instead of erroring.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from main.app.domain.communication.conversation_participant.service import (
    ConversationParticipantService,
)

CONVERSATION = "01a0b2355895792ea1686cd5804de1dd"
USER = "01a0b234-98ea-7939-85e6-26c300c772fd"


def _service(*, existing_first, winner_after_conflict=None, conflict=False):
    session = MagicMock()

    @asynccontextmanager
    async def _savepoint():
        yield

    session.begin_nested = _savepoint
    repo = MagicMock()
    repo._session = session
    repo.get_for = AsyncMock(side_effect=[existing_first, winner_after_conflict])
    if conflict:
        repo.create_return_model = AsyncMock(side_effect=IntegrityError("insert", {}, Exception()))
    else:
        repo.create_return_model = AsyncMock(return_value="created")
    service = object.__new__(ConversationParticipantService)
    service._participant_repo = repo
    return service, repo


async def _ensure(service):
    # Bypass the `@transactional` wrapper: the behaviour under test is the method body.
    method = ConversationParticipantService.ensure_participant
    method = getattr(method, "__wrapped__", method)
    return await method(service, CONVERSATION, USER, "ADMIN")


class TestEnsureParticipant:
    async def test_an_existing_member_is_returned_untouched(self):
        service, repo = _service(existing_first="already-there")
        assert await _ensure(service) == "already-there"
        repo.create_return_model.assert_not_awaited()

    async def test_a_new_member_is_created(self):
        service, repo = _service(existing_first=None)
        assert await _ensure(service) == "created"
        repo.create_return_model.assert_awaited_once()

    async def test_losing_the_insert_race_returns_the_winners_row(self):
        service, repo = _service(existing_first=None, winner_after_conflict="winner", conflict=True)
        assert await _ensure(service) == "winner"

    async def test_a_conflict_with_no_winner_is_not_swallowed(self):
        service, repo = _service(existing_first=None, winner_after_conflict=None, conflict=True)
        with pytest.raises(IntegrityError):
            await _ensure(service)
