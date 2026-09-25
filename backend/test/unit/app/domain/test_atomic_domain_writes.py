"""Domain writes computed in one SQL statement, so concurrent requests cannot lose an update.

Each of these was a read-modify-write in Python: two requests read the same value, each
wrote its own result, and one change vanished — a persona grant (an authorization bug), a
credit or debit on a balance, a second use of a single-use reset link, a missed-turn count,
a read marker moved backwards. The statement now does the arithmetic against the row as
committed, and Postgres serialises concurrent writers of that row.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.communication.assistant.session.models import AssistantSession
from main.app.domain.communication.assistant.session.repo import AssistantSessionRepo
from main.app.domain.communication.conversation_participant.models import ConversationParticipant
from main.app.domain.communication.conversation_participant.repo import ConversationParticipantRepo
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.auth.session.repo import PasswordResetTokenRepo
from main.app.domain.user.repo import UserRepo
from main.appodus_utils.db.session import db_session_ctx

USER_ID = "0199a000-0000-7000-8000-0000000000aa"
AT = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session():
    s = MagicMock()
    s.statements = []

    async def _execute(stmt, *args, **kwargs):
        s.statements.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalar.return_value = None
        result.scalar_one.return_value = 2
        return result

    s.execute = AsyncMock(side_effect=_execute)
    s.flush = AsyncMock()
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


def _sql(stmt) -> str:
    return " ".join(str(_compiled(stmt)).split())


class TestPersonaGrant:
    async def test_append_happens_in_sql_and_only_when_absent(self, session):
        await UserRepo(db=None).add_persona(USER_ID, UserPersona.AGENT)

        [stmt] = session.statements
        sql = _sql(stmt)
        assert sql.startswith("UPDATE users SET personas=(users.personas || ")
        # Only a row that lacks the persona is written, so a repeat grant is a no-op and a
        # concurrent grant of another persona is appended to, never overwritten.
        assert "NOT (users.personas @> " in sql
        assert "RETURNING" in sql
        params = _compiled(stmt).params
        assert [UserPersona.AGENT.value] in params.values()


class TestCreditBalance:
    async def test_credit_adds_in_sql(self, session):
        await UserRepo(db=None).add_credit_balance(USER_ID, 500)

        sql = _sql(session.statements[0])
        assert "SET credit_balance_kobo=(coalesce(users.credit_balance_kobo, %(coalesce_1)s) + %(coalesce_2)s)" in sql

    async def test_spend_never_drives_the_balance_below_zero(self, session):
        await UserRepo(db=None).spend_credit_balance(USER_ID, 500)

        sql = _sql(session.statements[0])
        assert "SET credit_balance_kobo=(coalesce(users.credit_balance_kobo, %(coalesce_1)s) - least(" in sql


class TestPasswordResetConsume:
    async def test_consume_is_a_conditional_update(self, session):
        assert await PasswordResetTokenRepo(db=None).consume("hash-1", AT) is None

        [stmt] = session.statements
        sql = _sql(stmt)
        assert sql.startswith("UPDATE password_reset_tokens SET consumed_at=")
        assert "password_reset_tokens.token_hash = %(token_hash_1)s" in sql
        # A token already used, or expired, is not consumed again.
        assert "password_reset_tokens.consumed_at IS NULL" in sql
        assert "password_reset_tokens.expires_at IS NULL OR password_reset_tokens.expires_at > " in sql
        assert "RETURNING" in sql


class TestAssistantMissCounter:
    async def test_miss_is_counted_in_sql(self, session):
        row = AssistantSession(id=uuid.uuid4(), unmatched_count=1)

        count = await AssistantSessionRepo(db=None).count_unmatched(row)

        assert count == 2
        # The loaded row shows the count without being marked dirty, so a later flush of
        # the same session cannot write a stale value back over a concurrent miss.
        assert row.unmatched_count == 2
        sql = _sql(session.statements[0])
        assert "SET unmatched_count=(coalesce(chat_bot_sessions.unmatched_count, %(coalesce_1)s) + %(coalesce_2)s)" in sql
        assert "RETURNING chat_bot_sessions.unmatched_count" in sql


class TestReadMarker:
    async def test_marker_only_moves_forward(self, session):
        membership = ConversationParticipant(id=uuid.uuid4(), last_read_at=None)

        moved = await ConversationParticipantRepo(db=None).advance_read(membership, AT)

        assert moved is False
        sql = _sql(session.statements[0])
        assert sql.startswith("UPDATE conversation_participants SET last_read_at=")
        # A late receipt must never pull the marker backwards past a newer read.
        assert "conversation_participants.last_read_at IS NULL OR conversation_participants.last_read_at < " in sql
