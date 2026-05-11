"""Unit tests for TaskReviewService — approve, reject, reopen (S28)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.task.models import Task, TaskRole, TaskStatus
from main.app.domain.verification.task.review.service import TaskReviewService, _MIN_REASON_LENGTH
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)


# ── fixtures ───────────────────────────────────────────────────────────────────


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


def _task(
    task_id: str = "task-1",
    verification_id: str = "ver-1",
    role: str = TaskRole.FIELD.value,
    status: str = TaskStatus.SUBMITTED.value,
) -> Task:
    t = MagicMock(spec=Task)
    t.id = task_id
    t.verification_id = verification_id
    t.role = role
    t.status = status
    t.agent_id = "agent-1"
    t.date_created = datetime.now(timezone.utc)
    t.date_updated = datetime.now(timezone.utc)
    return t


def _make_service(task: Task | None = None):
    task_repo = MagicMock()
    task_repo.get_task = AsyncMock(return_value=task or _task())
    task_repo.update = AsyncMock()

    audit = MagicMock()
    audit.schedule = MagicMock()

    svc = TaskReviewService(task_repo=task_repo, audit=audit)
    return svc, task_repo, audit


# ── approve ────────────────────────────────────────────────────────────────────


class TestApprove:
    @pytest.mark.parametrize(
        "role",
        [TaskRole.FIELD, TaskRole.SURVEYOR, TaskRole.REGISTRY, TaskRole.LAWYER],
    )
    async def test_approve_transitions_submitted_to_approved_for_all_roles(self, role):
        task = _task(role=role.value, status=TaskStatus.SUBMITTED.value)
        svc, repo, audit = _make_service(task)

        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            result = await svc.approve("task-1", "admin-1", note="Looks good")

        repo.update.assert_called_once()
        call_args = repo.update.call_args
        assert call_args[0][1].status == TaskStatus.APPROVED

        audit.schedule.assert_called_once()
        assert result.decision.value == "APPROVED"
        assert result.reviewed_by == "admin-1"

    async def test_approve_raises_when_task_not_submitted(self):
        task = _task(status=TaskStatus.IN_PROGRESS.value)
        svc, _, _ = _make_service(task)
        with pytest.raises(ValidationException):
            await svc.approve("task-1", "admin-1")

    async def test_approve_raises_when_task_not_found(self):
        svc, repo, _ = _make_service()
        repo.get_task = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.approve("missing-id", "admin-1")

    async def test_approve_emits_audit_log(self):
        svc, _, audit = _make_service()
        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            await svc.approve("task-1", "admin-1")
        audit.schedule.assert_called_once()
        call_kwargs = audit.schedule.call_args[1]
        assert call_kwargs["from_state"] == TaskStatus.SUBMITTED.value
        assert call_kwargs["to_state"] == TaskStatus.APPROVED.value

    async def test_approve_publishes_sse_event(self):
        svc, _, _ = _make_service()
        with patch.object(svc, "_derive_verification_status", AsyncMock()), \
             patch.object(svc, "_publish", AsyncMock()) as mock_pub:
            await svc.approve("task-1", "admin-1")
        mock_pub.assert_called_once_with("ver-1", "task_approved", "task-1")


# ── reject ─────────────────────────────────────────────────────────────────────


class TestReject:
    @pytest.mark.parametrize(
        "role",
        [TaskRole.FIELD, TaskRole.SURVEYOR, TaskRole.REGISTRY, TaskRole.LAWYER],
    )
    async def test_reject_returns_task_to_in_progress_for_all_roles(self, role):
        task = _task(role=role.value, status=TaskStatus.SUBMITTED.value)
        svc, repo, _ = _make_service(task)
        reason = "x" * _MIN_REASON_LENGTH

        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            result = await svc.reject("task-1", "admin-1", reason)

        assert repo.update.call_count == 2
        # first call → REJECTED, second call → IN_PROGRESS
        statuses = [c[0][1].status for c in repo.update.call_args_list]
        assert TaskStatus.REJECTED in statuses
        assert TaskStatus.IN_PROGRESS in statuses

        assert result.decision.value == "REJECTED"
        assert result.reason == reason

    async def test_reject_validates_min_reason_length(self):
        svc, _, _ = _make_service()
        short_reason = "too short"
        assert len(short_reason) < _MIN_REASON_LENGTH
        with pytest.raises(ValidationException, match="at least"):
            await svc.reject("task-1", "admin-1", short_reason)

    async def test_reject_exact_min_length_passes(self):
        svc, _, _ = _make_service()
        reason = "a" * _MIN_REASON_LENGTH
        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            result = await svc.reject("task-1", "admin-1", reason)
        assert result.reason == reason

    async def test_reject_raises_when_task_not_submitted(self):
        task = _task(status=TaskStatus.APPROVED.value)
        svc, _, _ = _make_service(task)
        with pytest.raises(ValidationException):
            await svc.reject("task-1", "admin-1", "a" * _MIN_REASON_LENGTH)

    async def test_reject_emits_audit_log(self):
        svc, _, audit = _make_service()
        reason = "b" * _MIN_REASON_LENGTH
        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            await svc.reject("task-1", "admin-1", reason)
        audit.schedule.assert_called_once()


# ── reopen ─────────────────────────────────────────────────────────────────────


class TestReopen:
    async def test_reopen_approved_task_returns_to_in_progress(self):
        task = _task(status=TaskStatus.APPROVED.value)
        svc, repo, _ = _make_service(task)
        reason = "c" * _MIN_REASON_LENGTH

        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            result = await svc.reopen("task-1", "admin-1", reason)

        repo.update.assert_called_once()
        assert repo.update.call_args[0][1].status == TaskStatus.IN_PROGRESS
        assert result.reason == reason

    async def test_reopen_validates_min_reason_length(self):
        task = _task(status=TaskStatus.APPROVED.value)
        svc, _, _ = _make_service(task)
        with pytest.raises(ValidationException, match="at least"):
            await svc.reopen("task-1", "admin-1", "short")

    async def test_reopen_raises_when_task_not_approved(self):
        task = _task(status=TaskStatus.SUBMITTED.value)
        svc, _, _ = _make_service(task)
        with pytest.raises(ValidationException, match="APPROVED"):
            await svc.reopen("task-1", "admin-1", "a" * _MIN_REASON_LENGTH)

    async def test_reopen_raises_when_task_not_found(self):
        svc, repo, _ = _make_service()
        repo.get_task = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.reopen("missing", "admin-1", "a" * _MIN_REASON_LENGTH)

    async def test_reopen_emits_audit_log(self):
        task = _task(status=TaskStatus.APPROVED.value)
        svc, _, audit = _make_service(task)
        with patch.object(svc, "_derive_verification_status", AsyncMock()):
            await svc.reopen("task-1", "admin-1", "d" * _MIN_REASON_LENGTH)
        audit.schedule.assert_called_once()
        call_kwargs = audit.schedule.call_args[1]
        assert call_kwargs["from_state"] == TaskStatus.APPROVED.value
        assert call_kwargs["to_state"] == TaskStatus.IN_PROGRESS.value
