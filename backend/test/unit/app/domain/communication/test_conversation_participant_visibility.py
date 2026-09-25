"""The participant visibility window (PRD §26.8, §26.4.4).

A customer who links a WhatsApp number sees that thread only from the moment they linked it —
earlier messages may belong to a previous holder of the number — and keeps read-only history
up to the moment the number is released. `is_unread` is the rule every unread count applies.
"""
from datetime import datetime, timedelta, timezone

import pytest

from main.app.domain.communication.conversation_participant.models import (
    ConversationParticipant,
    is_unread,
)

T0 = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


class TestIsUnread:
    def test_a_thread_with_no_messages_is_never_unread(self):
        assert is_unread(last_message_at=None, last_read_at=None) is False

    def test_an_unopened_thread_with_a_message_is_unread(self):
        assert is_unread(last_message_at=_at(5), last_read_at=None) is True

    def test_reading_after_the_last_message_clears_it(self):
        assert is_unread(last_message_at=_at(5), last_read_at=_at(6)) is False

    def test_a_newer_message_than_the_last_read_is_unread(self):
        assert is_unread(last_message_at=_at(7), last_read_at=_at(6)) is True

    def test_nothing_since_linking_is_not_unread(self):
        """The thread's latest message predates the link, so the customer cannot see it."""
        assert is_unread(last_message_at=_at(5), last_read_at=None, visible_from=_at(10)) is False

    def test_a_message_after_linking_is_unread(self):
        assert is_unread(last_message_at=_at(15), last_read_at=None, visible_from=_at(10)) is True

    def test_messages_after_release_do_not_count(self):
        """After unlinking the thread keeps moving for the agents; once the old owner has read
        up to the release, new messages they can no longer open must not badge it again."""
        assert is_unread(
            last_message_at=_at(30), last_read_at=_at(26),
            visible_from=_at(10), visible_until=_at(25),
        ) is False

    def test_history_that_may_be_unread_stays_unread_until_opened(self):
        """The thread only records its latest message, so the release time is an upper bound
        on what the owner could have missed. Erring towards unread is the safe direction —
        the other would hide a message they never saw."""
        assert is_unread(
            last_message_at=_at(30), last_read_at=_at(12),
            visible_from=_at(10), visible_until=_at(25),
        ) is True


def test_a_closed_window_makes_the_participant_read_only():
    participant = ConversationParticipant(visible_from=_at(0), visible_until=_at(5))
    assert participant.is_read_only is True


def test_an_open_or_absent_window_is_writable():
    assert ConversationParticipant(visible_from=_at(0)).is_read_only is False
    assert ConversationParticipant().is_read_only is False


class TestAdvanceRead:
    """Reading on WhatsApp counts as reading the thread (§26.8, D92): a read receipt, or the
    customer writing back, moves their portal read state forward — never backwards, and
    never into a window they no longer hold."""

    @pytest.fixture(autouse=True)
    def mock_db_session(self):
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, MagicMock

        from main.appodus_utils.db.session import db_session_ctx

        session = MagicMock()
        session.in_transaction.return_value = False

        @asynccontextmanager
        async def _begin():
            yield

        session.begin = _begin
        session.flush = AsyncMock()
        token = db_session_ctx.set(session)
        yield
        db_session_ctx.reset(token)

    @staticmethod
    def _service(membership):
        from unittest.mock import AsyncMock, MagicMock

        from main.app.domain.communication.conversation_participant.service import (
            ConversationParticipantService,
        )

        async def _advance_read(row, at):
            # The repo's conditional UPDATE, in memory: only ever forward.
            if row.last_read_at is not None and row.last_read_at >= at:
                return False
            row.last_read_at = at
            return True

        svc = object.__new__(ConversationParticipantService)
        svc._participant_repo = MagicMock(
            get_for=AsyncMock(return_value=membership),
            advance_read=AsyncMock(side_effect=_advance_read),
            _session=MagicMock(),
        )
        return svc

    async def test_it_moves_the_read_time_forward(self):
        membership = ConversationParticipant(visible_from=_at(0), last_read_at=_at(5))

        assert await self._service(membership).advance_read("conv-1", "cust-1", _at(9)) is True
        assert membership.last_read_at == _at(9)

    async def test_an_older_read_never_rewinds_it(self):
        membership = ConversationParticipant(visible_from=_at(0), last_read_at=_at(9))

        assert await self._service(membership).advance_read("conv-1", "cust-1", _at(5)) is False
        assert membership.last_read_at == _at(9)

    async def test_a_closed_window_or_no_membership_is_left_alone(self):
        released = ConversationParticipant(visible_from=_at(0), visible_until=_at(3))

        assert await self._service(released).advance_read("conv-1", "cust-1", _at(9)) is False
        assert released.last_read_at is None
        assert await self._service(None).advance_read("conv-1", "cust-1", _at(9)) is False

    async def test_a_read_before_the_window_opened_is_not_this_members(self):
        membership = ConversationParticipant(visible_from=_at(10))

        assert await self._service(membership).advance_read("conv-1", "cust-1", _at(5)) is False
        assert membership.last_read_at is None
