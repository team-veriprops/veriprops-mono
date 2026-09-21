"""Communication repo queries whose correctness is the WHERE clause itself."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.communication.chat_message.repo import ChatMessageRepo
from main.app.domain.communication.conversation.models import AdminInboxFilter
from main.app.domain.communication.conversation.repo import ConversationRepo
from main.app.domain.communication.conversation_participant.repo import (
    ConversationParticipantRepo,
)
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def captured_statements():
    """Record what the repo executes; the rows it would return are irrelevant here."""
    statements = []
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    result.scalar.return_value = 0

    async def _execute(stmt):
        statements.append(stmt)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)
    token = db_session_ctx.set(session)
    yield statements
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


async def test_general_support_lookup_never_returns_a_whatsapp_thread(captured_statements):
    """A linked number's WhatsApp thread is also `GENERAL_SUPPORT` with the account as
    `created_by`. Without a channel filter the web support lookup matched both rows and
    `.first()` picked one arbitrarily, so `/portal/support` could open the WhatsApp thread."""
    repo = object.__new__(ConversationRepo)

    await repo.get_general_support("user-1")

    sql = _sql(captured_statements[0])
    assert "conversations.channel = 'WEB'" in sql
    assert "conversations.type = 'GENERAL_SUPPORT'" in sql


async def test_the_chat_counter_respects_the_visibility_window(captured_statements):
    """The SQL twin of `is_unread`: capped at `visible_until`, ignoring anything before
    `visible_from`, so a released or freshly linked WhatsApp thread cannot badge forever."""
    repo = object.__new__(ConversationParticipantRepo)

    await repo.unread_conversation_count("user-1")

    sql = _sql(captured_statements[0])
    assert "visible_until" in sql
    assert "visible_from" in sql


async def test_a_viewer_with_a_window_sees_only_messages_inside_it(captured_statements):
    repo = object.__new__(ChatMessageRepo)
    linked = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    released = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

    await repo.list_delivered_page(
        "conv-1", "user-1", 0, 30, visible_from=linked, visible_until=released
    )

    # Both the count and the page read carry the window.
    for stmt in captured_statements:
        sql = _sql(stmt)
        assert "chat_messages.date_created >= '2026-09-16 12:00:00+00:00'" in sql
        assert "chat_messages.date_created <= '2026-09-17 12:00:00+00:00'" in sql


async def test_a_viewer_without_a_window_sees_the_whole_thread(captured_statements):
    repo = object.__new__(ChatMessageRepo)

    await repo.list_delivered_page("conv-1", "admin-1", 0, 30)

    assert all("date_created >=" not in _sql(stmt) for stmt in captured_statements)


ADMIN_ID = "9a1b2c3d-0000-4000-8000-00000000000a"


class TestAdminInbox:
    """The admin Conversations inbox (§16.5): one server-paged query whose scope, search and
    per-admin read state are all SQL — the list and the Chat counter must never disagree."""

    async def test_the_page_joins_this_admins_own_read_state_in_the_same_query(self, captured_statements):
        repo = object.__new__(ConversationRepo)

        await repo.list_admin_inbox_page(ADMIN_ID, 2, 10)

        count_sql, page_sql = (_sql(s) for s in captured_statements)
        # One query for the rows, not one participant lookup per thread.
        assert "LEFT OUTER JOIN conversation_participants" in page_sql
        assert f"conversation_participants.user_id = '{ADMIN_ID}'" in page_sql
        assert "ORDER BY conversations.last_message_at DESC" in page_sql
        assert "LIMIT 10 OFFSET 20" in page_sql
        assert "count(" in count_sql

    async def test_every_thread_is_in_scope_by_default_including_web_support(self, captured_statements):
        """Web support threads were missing from the console entirely before this inbox."""
        repo = object.__new__(ConversationRepo)

        await repo.list_admin_inbox_page(ADMIN_ID, 0, 10)

        page_sql = _sql(captured_statements[1])
        assert "conversations.type" not in page_sql.split("WHERE", 1)[1]
        assert "conversations.channel" not in page_sql.split("WHERE", 1)[1]
        assert "conversations.last_message_at IS NOT NULL" in page_sql

    @pytest.mark.parametrize(
        "inbox_filter, expected",
        [
            (AdminInboxFilter.SUPPORT, ["conversations.type = 'GENERAL_SUPPORT'", "conversations.channel = 'WEB'"]),
            (AdminInboxFilter.WHATSAPP, ["conversations.channel = 'WHATSAPP'"]),
            (AdminInboxFilter.CASES, ["conversations.type IN ('CUSTOMER_ADMIN', 'ADMIN_AGENT')"]),
        ],
    )
    async def test_a_filter_narrows_the_scope_in_sql(self, captured_statements, inbox_filter, expected):
        repo = object.__new__(ConversationRepo)

        await repo.list_admin_inbox_page(ADMIN_ID, 0, 10, inbox_filter=inbox_filter)

        for stmt in captured_statements:  # the total and the page agree
            sql = _sql(stmt)
            for clause in expected:
                assert clause in sql

    async def test_search_matches_the_number_the_subject_and_the_owner(self, captured_statements):
        repo = object.__new__(ConversationRepo)

        await repo.list_admin_inbox_page(ADMIN_ID, 0, 10, query="  ada  ")

        for stmt in captured_statements:
            # The pyformat dialect escapes a literal % as %%.
            sql = _sql(stmt).replace("%%", "%")
            assert "conversations.external_ref ILIKE '%ada%'" in sql
            assert "conversations.subject ILIKE '%ada%'" in sql
            assert "users.email ILIKE '%ada%'" in sql

    async def test_the_owner_is_only_resolved_for_support_threads(self, captured_statements):
        """A case thread's `created_by` is whoever opened it first — often an admin — so it
        would label the thread with the wrong person."""
        repo = object.__new__(ConversationRepo)

        await repo.list_admin_inbox_page(ADMIN_ID, 0, 10)

        page_sql = _sql(captured_statements[1])
        users_join = page_sql.split("LEFT OUTER JOIN users ON", 1)[1].split("WHERE", 1)[0]
        assert "conversations.type = 'GENERAL_SUPPORT'" in users_join

    async def test_the_counter_uses_the_same_unread_rule_as_the_member_counter(self, captured_statements):
        repo = object.__new__(ConversationRepo)

        count = await repo.count_admin_unread(ADMIN_ID)

        sql = _sql(captured_statements[0])
        assert count == 0
        assert f"conversation_participants.user_id = '{ADMIN_ID}'" in sql
        assert "conversation_participants.last_read_at IS NULL" in sql
        assert "visible_until" in sql


async def test_support_read_time_is_the_latest_read_by_any_admin(captured_statements):
    """Admins are a shared inbox, so "seen by support" means any admin, not a named one."""
    repo = object.__new__(ConversationParticipantRepo)

    await repo.latest_admin_read_at("conv-1")

    sql = _sql(captured_statements[0])
    assert "max(conversation_participants.last_read_at)" in sql
    assert "users.user_type = 'ADMIN'" in sql


async def test_a_reply_cancelled_by_an_in_portal_read_is_not_queued_for_the_phone(captured_statements):
    repo = object.__new__(ChatMessageRepo)

    await repo.list_pending_channel_delivery("conv-1")

    sql = _sql(captured_statements[0])
    assert "chat_messages.channel_status != 'CANCELLED'" in sql


async def test_a_receipt_never_matches_a_customers_own_inbound(captured_statements):
    repo = object.__new__(ChatMessageRepo)

    await repo.get_outbound_by_external_id("wamid.OUT1")

    sql = _sql(captured_statements[0])
    assert "chat_messages.external_message_id = 'wamid.OUT1'" in sql
    assert "chat_messages.sender_kind != 'CUSTOMER'" in sql


class TestAssistantTurnClaim:
    """D93 — a deferred web turn is claimed by one conditional UPDATE, so two requests can
    never both answer it; a claim left by a request that died can be taken over."""

    async def test_the_claim_is_one_conditional_update_that_returns_the_message(self, captured_statements):
        from main.app.domain.communication.assistant.session.repo import AssistantSessionRepo

        repo = object.__new__(AssistantSessionRepo)
        now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
        stale = datetime(2026, 9, 17, 11, 59, 36, tzinfo=timezone.utc)

        await repo.claim_pending_turn("c0ffee00000000000000000000000001", now=now, stale_before=stale)

        [statement] = captured_statements
        sql = _sql(statement)
        assert sql.startswith("UPDATE chat_bot_sessions SET turn_claimed_at=")
        assert "chat_bot_sessions.pending_turn_message_id IS NOT NULL" in sql
        assert "chat_bot_sessions.turn_claimed_at IS NULL OR chat_bot_sessions.turn_claimed_at < '2026-09-17 11:59:36+00:00'" in sql
        assert "RETURNING chat_bot_sessions.pending_turn_message_id" in sql

    async def test_the_sweep_leaves_a_fresh_turn_to_the_customers_own_request(self, captured_statements):
        from main.app.domain.communication.assistant.session.repo import AssistantSessionRepo

        repo = object.__new__(AssistantSessionRepo)
        waiting = datetime(2026, 9, 17, 11, 59, 52, tzinfo=timezone.utc)
        stale = datetime(2026, 9, 17, 11, 59, 36, tzinfo=timezone.utc)

        await repo.list_claimable_turns(waiting_before=waiting, stale_before=stale, limit=20)

        sql = _sql(captured_statements[0])
        assert "chat_bot_sessions.pending_turn_at < '2026-09-17 11:59:52+00:00'" in sql
        assert "LIMIT 20" in sql
