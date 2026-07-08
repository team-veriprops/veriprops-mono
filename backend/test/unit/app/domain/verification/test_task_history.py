"""Unit tests for agent task-history read — S23 (R19.3)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _svc(task):
    svc = object.__new__(VerificationTaskService)
    svc._task_repo = MagicMock()
    svc._task_repo.get_model = AsyncMock(return_value=task)
    svc._audit = MagicMock()
    svc._audit.get_activity_log = AsyncMock(return_value="activity-page")
    return svc


class TestTaskHistory:
    async def test_owner_gets_activity_via_audit_read_model(self):
        task = SimpleNamespace(id="task-1", assigned_agent_id="agent-1")
        svc = _svc(task)
        result = await svc.task_history("task-1", "agent-1", page=0, page_size=20)

        assert result == "activity-page"
        svc._audit.get_activity_log.assert_awaited_once_with(
            resource_type="verification_task", resource_id="task-1", page=0, page_size=20
        )

    async def test_non_owner_is_rejected(self):
        task = SimpleNamespace(id="task-1", assigned_agent_id="agent-1")
        svc = _svc(task)
        with pytest.raises(ValidationException):
            await svc.task_history("task-1", "someone-else")
        svc._audit.get_activity_log.assert_not_awaited()
