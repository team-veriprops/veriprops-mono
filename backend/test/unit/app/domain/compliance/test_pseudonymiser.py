"""Unit tests for PiiPseudonymiser — S23 (§4.11)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.compliance.erasure.pseudonymiser import PiiPseudonymiser
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


class TestTokenFor:
    def test_is_stable_for_the_same_subject(self):
        p = PiiPseudonymiser()
        assert p.token_for("user-1") == p.token_for("user-1")

    def test_differs_between_subjects_and_is_opaque(self):
        p = PiiPseudonymiser()
        t1, t2 = p.token_for("user-1"), p.token_for("user-2")
        assert t1 != t2
        assert t1.startswith("erased-")
        assert "user-1" not in t1  # opaque — the raw id is not recoverable from the token


def _linked(session, phones):
    """Make the subject's linked-number lookup answer with *phones*.

    The channel keys on a phone number rather than a user id, so the pseudonymiser reads
    the links first and scrubs by number — the one SELECT among the UPDATEs.
    """
    result = MagicMock()
    result.all.return_value = [(phone,) for phone in phones]
    session.execute = AsyncMock(return_value=result)


class TestPseudonymise:
    async def test_scrubs_every_identity_surface(self, mock_session):
        _linked(mock_session, [])
        p = PiiPseudonymiser()
        surfaces = await p.pseudonymise("user-9", "erased-xyz")

        # The audit actor is severed among them (§4.11).
        assert "users" in surfaces
        assert "audit_logs" in surfaces
        assert "device_sessions" in surfaces

    async def test_a_subject_who_never_linked_a_number_stops_at_the_link_table(
        self, mock_session
    ):
        # Everything downstream in the channel keys on a phone number, so there is nothing
        # to scrub — and issuing `IN ()` updates against an empty list would be five
        # pointless statements on every erasure the platform runs.
        _linked(mock_session, [])
        surfaces = await PiiPseudonymiser().pseudonymise("user-9", "erased-xyz")

        assert "whatsapp_links" in surfaces
        assert "whatsapp_inbound_messages" not in surfaces

    async def test_assistant_sessions_are_scrubbed_even_without_a_number(self, mock_session):
        """A web support or case thread holds the same half-finished intake answers as a
        WhatsApp one (D93), and has no number to find it by."""
        _linked(mock_session, [])
        surfaces = await PiiPseudonymiser().pseudonymise("user-9", "erased-xyz")

        assert "chat_bot_sessions" in surfaces

    async def test_the_whole_whatsapp_channel_is_scrubbed_for_a_linked_subject(
        self, mock_session
    ):
        """§26.8 — none of these were covered before S11, so an approved erasure left the
        subject's number in five places, and their half-finished chat intake in a sixth."""
        _linked(mock_session, ["+2348012345678"])
        surfaces = await PiiPseudonymiser().pseudonymise("user-9", "erased-xyz")

        for surface in (
            "whatsapp_links",
            "chat_bot_sessions",
            "whatsapp_inbound_messages",
            "case_delegates",
            "handoff_token_redemptions",
        ):
            assert surface in surfaces, surface

    async def test_every_surface_is_one_statement_plus_the_lookup(self, mock_session):
        _linked(mock_session, ["+2348012345678"])
        p = PiiPseudonymiser()
        surfaces = await p.pseudonymise("user-9", "erased-xyz")

        # One UPDATE per surface, plus the single SELECT that reads the subject's numbers.
        assert mock_session.execute.await_count == len(surfaces) + 1

    async def test_the_assistant_session_is_reset_not_just_renumbered(self, mock_session):
        """Sessions are keyed by conversation now (D93), and a WhatsApp conversation's row
        outlives erasure (§26.8 retains the content) — so the next message from this number
        would find the *same* session, already welcomed, and resume the old conversation
        exactly where it left off unless its memory is cleared too."""
        from sqlalchemy.dialects import postgresql

        _linked(mock_session, ["+2348012345678"])
        statements = []
        real_execute = mock_session.execute

        async def _capture(stmt, *args, **kwargs):
            statements.append(stmt)
            return await real_execute(stmt, *args, **kwargs)

        mock_session.execute = AsyncMock(side_effect=_capture)

        await PiiPseudonymiser().pseudonymise("user-9", "erased-xyz")

        updates = [str(s.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
                   for s in statements if getattr(s, "table", None) is not None]
        [sql] = [s for s in updates if s.startswith("UPDATE chat_bot_sessions")]
        for reset_to_blank in ("welcomed_at", "last_inbound_at", "current_flow", "unmatched_count"):
            assert f"{reset_to_blank}=NULL" in sql or f"{reset_to_blank}=0" in sql, sql
