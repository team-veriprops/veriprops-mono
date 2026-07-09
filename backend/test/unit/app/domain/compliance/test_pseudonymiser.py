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


class TestPseudonymise:
    async def test_scrubs_every_pii_surface(self, mock_session):
        p = PiiPseudonymiser()
        surfaces = await p.pseudonymise("user-9", "erased-xyz")

        # Each surface is one bulk UPDATE; the audit actor is severed among them (§4.11).
        assert "users" in surfaces
        assert "audit_logs" in surfaces
        assert "device_sessions" in surfaces
        assert mock_session.execute.await_count == len(surfaces)
