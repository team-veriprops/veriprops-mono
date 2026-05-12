"""Unit tests for agent availability auto-flip on task accept/release (S50)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.agent.models import AvailabilityStatus, UpdateAgentApplicationDto
from main.app.domain.verification.task.service import TaskService
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


def _make_app(availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE, app_id="app-1"):
    app = MagicMock()
    app.id = app_id
    app.availability_status = availability.value
    return app


def _make_svc(active_task_count: int, max_tasks: int = 5, agent_app=None):
    """Construct a TaskService with mocked repos for availability tests."""
    tasks = MagicMock()
    tasks.count_active_for_agent = AsyncMock(return_value=active_task_count)

    agent_apps = MagicMock()
    agent_apps.get_by_user_id = AsyncMock(return_value=agent_app or _make_app())
    agent_apps.update = AsyncMock()

    config = MagicMock()
    config.get_int = AsyncMock(return_value=max_tasks)

    svc = TaskService.__new__(TaskService)
    svc._tasks = tasks
    svc._agent_apps = agent_apps
    svc._config = config
    # Other deps not needed for these methods
    return svc, agent_apps


class TestMaybeFlipUnavailable:
    async def test_flips_to_unavailable_when_at_cap(self):
        app = _make_app(AvailabilityStatus.AVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=5, max_tasks=5, agent_app=app)

        await svc._maybe_flip_unavailable("agent-1")

        agent_apps.update.assert_awaited_once()
        _, dto = agent_apps.update.call_args[0]
        assert isinstance(dto, UpdateAgentApplicationDto)
        assert dto.availability_status == AvailabilityStatus.UNAVAILABLE.value

    async def test_flips_to_unavailable_when_over_cap(self):
        app = _make_app(AvailabilityStatus.AVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=7, max_tasks=5, agent_app=app)

        await svc._maybe_flip_unavailable("agent-1")

        agent_apps.update.assert_awaited_once()

    async def test_does_not_flip_below_cap(self):
        app = _make_app(AvailabilityStatus.AVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=4, max_tasks=5, agent_app=app)

        await svc._maybe_flip_unavailable("agent-1")

        agent_apps.update.assert_not_awaited()

    async def test_does_not_flip_if_already_unavailable(self):
        app = _make_app(AvailabilityStatus.UNAVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=5, max_tasks=5, agent_app=app)

        await svc._maybe_flip_unavailable("agent-1")

        agent_apps.update.assert_not_awaited()

    async def test_does_not_flip_if_no_application(self):
        svc, agent_apps = _make_svc(active_task_count=5)
        agent_apps.get_by_user_id = AsyncMock(return_value=None)

        await svc._maybe_flip_unavailable("agent-1")

        agent_apps.update.assert_not_awaited()


class TestMaybeRestoreAvailability:
    async def test_restores_unavailable_when_below_cap(self):
        app = _make_app(AvailabilityStatus.UNAVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=4, max_tasks=5, agent_app=app)

        await svc._maybe_restore_availability("agent-1")

        agent_apps.update.assert_awaited_once()
        _, dto = agent_apps.update.call_args[0]
        assert dto.availability_status == AvailabilityStatus.AVAILABLE.value

    async def test_does_not_restore_if_still_at_cap(self):
        app = _make_app(AvailabilityStatus.UNAVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=5, max_tasks=5, agent_app=app)

        await svc._maybe_restore_availability("agent-1")

        agent_apps.update.assert_not_awaited()

    async def test_does_not_restore_limited_status(self):
        # LIMITED is manually set — don't auto-restore
        app = _make_app(AvailabilityStatus.LIMITED)
        svc, agent_apps = _make_svc(active_task_count=2, max_tasks=5, agent_app=app)

        await svc._maybe_restore_availability("agent-1")

        agent_apps.update.assert_not_awaited()

    async def test_does_not_restore_if_already_available(self):
        app = _make_app(AvailabilityStatus.AVAILABLE)
        svc, agent_apps = _make_svc(active_task_count=2, max_tasks=5, agent_app=app)

        await svc._maybe_restore_availability("agent-1")

        agent_apps.update.assert_not_awaited()

    async def test_does_not_restore_if_no_application(self):
        svc, agent_apps = _make_svc(active_task_count=2)
        agent_apps.get_by_user_id = AsyncMock(return_value=None)

        await svc._maybe_restore_availability("agent-1")

        agent_apps.update.assert_not_awaited()
