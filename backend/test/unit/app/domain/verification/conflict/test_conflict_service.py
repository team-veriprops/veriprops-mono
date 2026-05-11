"""Unit tests for ConflictService (S29)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.conflict.models import (
    ConflictFlag,
    ConflictFlagDto,
    ConflictSeverity,
    ConflictStatus,
    ResolveConflictDto,
)
from main.app.domain.verification.conflict.service import ConflictService
from main.app.domain.verification.task.models import Task, TaskRole, TaskStatus
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)


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


def _conflict_flag(flag_id: str = "flag-1", status: str = ConflictStatus.OPEN.value) -> ConflictFlag:
    f = MagicMock(spec=ConflictFlag)
    f.id = flag_id
    f.verification_id = "ver-1"
    f.rule_id = "OCCUPANCY_MISMATCH"
    f.severity = ConflictSeverity.BLOCKER.value
    f.description = "Test conflict"
    f.status = status
    f.resolution_note = None
    f.resolved_by = None
    f.resolved_at = None
    f.date_created = datetime.now(timezone.utc)
    f.date_updated = None
    return f


def _task(role: str, payload: dict) -> Task:
    t = MagicMock(spec=Task)
    t.role = role
    t.status = TaskStatus.SUBMITTED.value
    t.draft_payload = json.dumps(payload)
    return t


def _make_service(flags=None, task_list=None, flag_for_get=None):
    conflict_repo = MagicMock()
    conflict_repo.list_for_verification = AsyncMock(return_value=flags or [])
    conflict_repo.has_open = AsyncMock(return_value=bool(flags))
    conflict_repo.create_return_model = AsyncMock(side_effect=lambda dto: _conflict_flag())
    conflict_repo.get_by_id = AsyncMock(return_value=flag_for_get or _conflict_flag())
    conflict_repo.update = AsyncMock()

    task_repo = MagicMock()
    task_repo.list_for_verification = AsyncMock(return_value=task_list or [])

    audit = MagicMock()
    audit.schedule = MagicMock()

    svc = ConflictService(conflict_repo=conflict_repo, task_repo=task_repo, audit=audit)
    return svc, conflict_repo, audit


class TestDetectAndStore:
    async def test_creates_flags_for_detected_conflicts(self):
        tasks = [
            _task(TaskRole.FIELD.value, {"occupancy_status": "VACANT"}),
            _task(TaskRole.REGISTRY.value, {"registered_occupancy": "OCCUPIED"}),
        ]
        svc, repo, _ = _make_service(task_list=tasks)

        with patch.object(svc, "_publish_conflict", AsyncMock()):
            flags = await svc.detect_and_store("ver-1")

        assert len(flags) >= 1
        assert repo.create_return_model.called

    async def test_no_flags_for_consistent_data(self):
        tasks = [
            _task(TaskRole.FIELD.value, {"occupancy_status": "OCCUPIED"}),
            _task(TaskRole.REGISTRY.value, {"registered_occupancy": "OCCUPIED"}),
        ]
        svc, repo, _ = _make_service(task_list=tasks)
        flags = await svc.detect_and_store("ver-1")
        assert flags == []
        repo.create_return_model.assert_not_called()

    async def test_publishes_sse_event_when_conflicts_found(self):
        tasks = [
            _task(TaskRole.FIELD.value, {"occupancy_status": "VACANT"}),
            _task(TaskRole.REGISTRY.value, {"registered_occupancy": "OCCUPIED"}),
        ]
        svc, _, _ = _make_service(task_list=tasks)

        with patch.object(svc, "_publish_conflict", AsyncMock()) as mock_pub:
            await svc.detect_and_store("ver-1")

        mock_pub.assert_called_once_with("ver-1")


class TestHasOpenConflicts:
    async def test_true_when_open_flags_exist(self):
        svc, repo, _ = _make_service(flags=[_conflict_flag()])
        repo.has_open = AsyncMock(return_value=True)
        assert await svc.has_open_conflicts("ver-1") is True

    async def test_false_when_no_open_flags(self):
        svc, repo, _ = _make_service(flags=[])
        repo.has_open = AsyncMock(return_value=False)
        assert await svc.has_open_conflicts("ver-1") is False


class TestResolveConflict:
    async def test_override_resolves_conflict(self):
        flag = _conflict_flag(status=ConflictStatus.OPEN.value)
        resolved_flag = _conflict_flag(status=ConflictStatus.OVERRIDDEN.value)
        svc, repo, audit = _make_service(flag_for_get=flag)
        repo.get_by_id = AsyncMock(side_effect=[flag, resolved_flag])

        result = await svc.resolve(
            "flag-1",
            "admin-1",
            ResolveConflictDto(action="OVERRIDE", note="Verified on-site, discrepancy acceptable"),
        )

        repo.update.assert_called_once()
        audit.schedule.assert_called_once()

    async def test_override_requires_note(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValidationException, match="note"):
            await svc.resolve(
                "flag-1",
                "admin-1",
                ResolveConflictDto(action="OVERRIDE", note=""),
            )

    async def test_raises_when_flag_not_found(self):
        svc, repo, _ = _make_service()
        repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.resolve("missing", "admin-1", ResolveConflictDto(action="OVERRIDE", note="note"))

    async def test_raises_when_already_resolved(self):
        flag = _conflict_flag(status=ConflictStatus.OVERRIDDEN.value)
        svc, repo, _ = _make_service(flag_for_get=flag)
        with pytest.raises(ValidationException, match="already resolved"):
            await svc.resolve("flag-1", "admin-1", ResolveConflictDto(action="OVERRIDE", note="note"))

    async def test_reject_task_action_requires_task_id(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValidationException, match="task_id_to_reject"):
            await svc.resolve(
                "flag-1",
                "admin-1",
                ResolveConflictDto(action="REJECT_TASK", note="bad data"),
            )
