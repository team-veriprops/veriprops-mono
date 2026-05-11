"""Unit tests for EscalationService — category enum, creation, SSE alert.

Covers:
- EscalationCategory enum has all PRD-required values
- report() persists escalation and returns DTO
- report() publishes SSE alert to Redis (non-fatal on failure)
- list_for_task() returns all escalations for a task
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.escalation.models import (
    Escalation,
    EscalationCategory,
    EscalationDto,
    ReportEscalationDto,
)
from main.app.domain.verification.escalation.service import EscalationService
from main.appodus_utils.db.session import db_session_ctx


# ── fixtures ──────────────────────────────────────────────────────────────────

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


def _make_escalation(
    task_id: str = "task-1",
    reporter_id: str = "agent-1",
    category: str = EscalationCategory.INACCESSIBLE.value,
) -> Escalation:
    esc = MagicMock(spec=Escalation)
    esc.id = "esc-1"
    esc.task_id = task_id
    esc.reporter_id = reporter_id
    esc.category = category
    esc.description = "Cannot access the property"
    esc.date_created = datetime.now(timezone.utc)
    esc.date_updated = datetime.now(timezone.utc)
    return esc


def _make_service(stored: Escalation | None = None, list_result: list | None = None):
    repo = MagicMock()
    repo.create_return_model = AsyncMock(return_value=stored or _make_escalation())
    repo.list_for_task = AsyncMock(return_value=list_result or [])
    return EscalationService(repo=repo)


# ── EscalationCategory enum coverage ─────────────────────────────────────────

class TestEscalationCategoryEnum:
    def test_inaccessible_exists(self):
        assert EscalationCategory.INACCESSIBLE in EscalationCategory

    def test_suspicious_exists(self):
        assert EscalationCategory.SUSPICIOUS in EscalationCategory

    def test_safety_exists(self):
        assert EscalationCategory.SAFETY in EscalationCategory

    def test_conflicting_exists(self):
        assert EscalationCategory.CONFLICTING in EscalationCategory

    def test_other_exists(self):
        assert EscalationCategory.OTHER in EscalationCategory


# ── report() ─────────────────────────────────────────────────────────────────

class TestReport:
    async def test_creates_escalation_record(self):
        svc = _make_service()
        dto = ReportEscalationDto(
            category=EscalationCategory.INACCESSIBLE,
            description="Gate is locked and owner unresponsive",
        )

        with patch("main.app.domain.verification.escalation.service.di") as mock_di:
            redis = MagicMock()
            redis.publish = AsyncMock()
            mock_di.__getitem__ = MagicMock(return_value=redis)
            result = await svc.report("task-1", "agent-1", dto)

        svc._repo.create_return_model.assert_awaited_once()
        assert isinstance(result, EscalationDto)
        assert result.task_id == "task-1"
        assert result.reporter_id == "agent-1"

    async def test_publishes_sse_to_admin_channel(self):
        svc = _make_service()
        dto = ReportEscalationDto(
            category=EscalationCategory.SUSPICIOUS,
            description="Signs of document fraud on site",
        )

        with patch("main.app.domain.verification.escalation.service.di") as mock_di:
            redis = MagicMock()
            redis.publish = AsyncMock()
            mock_di.__getitem__ = MagicMock(return_value=redis)
            await svc.report("task-1", "agent-1", dto)

        redis.publish.assert_awaited_once()
        channel, payload = redis.publish.call_args[0]
        assert channel == "admin:escalations"
        assert payload["event"] == "ESCALATION_CREATED"
        assert payload["task_id"] == "task-1"
        assert payload["category"] == EscalationCategory.SUSPICIOUS.value

    async def test_redis_failure_is_non_fatal(self):
        """SSE publish error must not bubble up — service returns DTO regardless."""
        svc = _make_service()
        dto = ReportEscalationDto(
            category=EscalationCategory.SAFETY,
            description="Dangerous site conditions",
        )

        with patch("main.app.domain.verification.escalation.service.di") as mock_di:
            redis = MagicMock()
            redis.publish = AsyncMock(side_effect=ConnectionError("Redis down"))
            mock_di.__getitem__ = MagicMock(return_value=redis)
            result = await svc.report("task-1", "agent-1", dto)

        # Must still return a valid DTO
        assert isinstance(result, EscalationDto)

    async def test_category_stored_correctly(self):
        stored = _make_escalation(category=EscalationCategory.CONFLICTING.value)
        svc = _make_service(stored=stored)
        dto = ReportEscalationDto(
            category=EscalationCategory.CONFLICTING,
            description="Conflicting title deeds",
        )

        with patch("main.app.domain.verification.escalation.service.di") as mock_di:
            redis = MagicMock()
            redis.publish = AsyncMock()
            mock_di.__getitem__ = MagicMock(return_value=redis)
            result = await svc.report("task-1", "agent-1", dto)

        assert result.category == EscalationCategory.CONFLICTING


# ── list_for_task() ───────────────────────────────────────────────────────────

class TestListForTask:
    async def test_returns_empty_when_none(self):
        svc = _make_service(list_result=[])

        with patch("main.app.domain.verification.escalation.service.di"):
            result = await svc.list_for_task("task-1")
        assert result == []

    async def test_returns_dtos_for_task(self):
        items = [_make_escalation("task-1"), _make_escalation("task-1")]
        svc = _make_service(list_result=items)

        with patch("main.app.domain.verification.escalation.service.di"):
            result = await svc.list_for_task("task-1")
        assert len(result) == 2
        assert all(isinstance(r, EscalationDto) for r in result)
