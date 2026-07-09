"""AdminNoteService (PRD §6.6) — internal operational notes on a verification. Repo mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.verification.admin_note.models import AddAdminNoteDto, AdminNoteCategory
from main.app.domain.verification.admin_note.service import AdminNoteService
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


def _service():
    svc = object.__new__(AdminNoteService)
    svc._admin_note_repo = MagicMock()
    return svc


class TestAdd:
    async def test_add_stamps_verification_and_author(self):
        svc = _service()
        svc._admin_note_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="note-1"))

        dto = AddAdminNoteDto(category=AdminNoteCategory.RISK, body="Flag: mismatched survey", pinned=True)
        result = await svc.add("vid-1", "admin-9", dto)

        assert result.id == "note-1"
        create_dto = svc._admin_note_repo.create_return_model.call_args.args[0]
        assert create_dto.verification_id == "vid-1"
        assert create_dto.author_id == "admin-9"
        assert create_dto.category == AdminNoteCategory.RISK
        assert create_dto.pinned is True

    async def test_add_defaults_category_operational(self):
        svc = _service()
        svc._admin_note_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="note-2"))

        await svc.add("vid-1", "admin-9", AddAdminNoteDto(body="routine"))

        create_dto = svc._admin_note_repo.create_return_model.call_args.args[0]
        assert create_dto.category == AdminNoteCategory.OPERATIONAL
        assert create_dto.pinned is False


class TestList:
    async def test_list_delegates_to_repo(self):
        svc = _service()
        rows = [SimpleNamespace(id="note-1"), SimpleNamespace(id="note-2")]
        svc._admin_note_repo.list_for_verification = AsyncMock(return_value=rows)

        assert await svc.list_for_verification("vid-1") == rows
        svc._admin_note_repo.list_for_verification.assert_awaited_once_with("vid-1")
