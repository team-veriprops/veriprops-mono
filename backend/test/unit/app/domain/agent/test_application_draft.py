"""AgentApplicationDraftService resumable-wizard lifecycle (PRD §3.1) — repo mocked.

Verifies the one-active-draft-per-user rule: create when none exists, update when
one does, and discard the active draft.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.agent.application_draft.models import SaveAgentApplicationDraftDto
from main.app.domain.user.agent.application_draft.service import AgentApplicationDraftService
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_service():
    svc = object.__new__(AgentApplicationDraftService)
    svc._draft_repo = MagicMock()
    svc._draft_repo.get_active_for_user = AsyncMock(return_value=None)
    svc._draft_repo.create = AsyncMock()
    svc._draft_repo.update = AsyncMock()
    svc._draft_repo.soft_delete = AsyncMock()
    return svc


class TestDraftResume:
    async def test_creates_draft_when_none(self):
        svc = _make_service()
        out = await svc.save_draft("u-1", SaveAgentApplicationDraftDto(step=2, payload={"roles": ["FIELD"]}))
        svc._draft_repo.create.assert_awaited_once()
        assert out.step == 2

    async def test_updates_existing_draft(self):
        svc = _make_service()
        svc._draft_repo.get_active_for_user = AsyncMock(return_value=SimpleNamespace(id="d-1"))
        await svc.save_draft("u-1", SaveAgentApplicationDraftDto(step=3, payload={}))
        svc._draft_repo.update.assert_awaited_once()


class TestDiscard:
    async def test_discards_active_draft(self):
        svc = _make_service()
        svc._draft_repo.get_active_for_user = AsyncMock(return_value=SimpleNamespace(id="d-1"))
        await svc.discard("u-1")
        svc._draft_repo.soft_delete.assert_awaited_once_with("d-1")

    async def test_noop_when_no_draft(self):
        svc = _make_service()
        await svc.discard("u-1")
        svc._draft_repo.soft_delete.assert_not_awaited()
