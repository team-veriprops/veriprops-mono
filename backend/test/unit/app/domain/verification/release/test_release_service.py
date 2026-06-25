"""Unit tests for ReleaseService (S31)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.release.service import ReleaseService
from main.app.domain.verification.task.models import TaskRole, TaskStatus
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


def _ver(status: str = VerificationStatus.UNDER_REVIEW.value):
    v = MagicMock()
    v.id = "ver-id-1"
    v.vid = "VID-001"
    v.status = status
    return v


def _task(role: str, status: str = TaskStatus.APPROVED.value):
    t = MagicMock()
    t.role = role
    t.status = status
    return t


def _make_service(ver=None, tasks=None, has_open_conflicts: bool = False):
    ver_repo = MagicMock()
    ver_repo.get_by_vid = AsyncMock(return_value=ver or _ver())
    ver_repo.update = AsyncMock()

    task_repo = MagicMock()
    task_repo.list_for_verification = AsyncMock(return_value=tasks or [])

    audit = MagicMock()
    audit.schedule = MagicMock()

    svc = ReleaseService(
        verification_repo=ver_repo,
        task_repo=task_repo,
        audit=audit,
    )
    return svc, ver_repo, task_repo, audit


class TestRelease:
    async def test_release_succeeds_when_all_approved_no_conflicts(self):
        tasks = [
            _task(TaskRole.REGISTRY.value, TaskStatus.APPROVED.value),
        ]
        svc, ver_repo, _, audit = _make_service(tasks=tasks)
        with patch.object(svc, "_has_open_conflicts", AsyncMock(return_value=False)), \
             patch.object(svc, "_publish", AsyncMock()):
            result = await svc.release("VID-001", "admin-1")

        assert result.status == VerificationStatus.COMPLETED.value
        ver_repo.update.assert_called_once()
        audit.schedule.assert_called_once()

    async def test_release_blocked_if_task_not_approved(self):
        tasks = [
            _task(TaskRole.REGISTRY.value, TaskStatus.SUBMITTED.value),
        ]
        svc, _, _, _ = _make_service(tasks=tasks)
        with patch.object(svc, "_has_open_conflicts", AsyncMock(return_value=False)), \
             pytest.raises(ValidationException, match="not yet approved"):
            await svc.release("VID-001", "admin-1")

    async def test_release_blocked_if_open_conflicts(self):
        tasks = [_task(TaskRole.REGISTRY.value, TaskStatus.APPROVED.value)]
        svc, _, _, _ = _make_service(tasks=tasks)
        with patch.object(svc, "_has_open_conflicts", AsyncMock(return_value=True)), \
             pytest.raises(ValidationException, match="conflict"):
            await svc.release("VID-001", "admin-1")

    async def test_release_raises_if_not_under_review(self):
        svc, _, _, _ = _make_service(ver=_ver(status=VerificationStatus.IN_PROGRESS.value))
        with pytest.raises(ValidationException, match="UNDER_REVIEW"):
            await svc.release("VID-001", "admin-1")

    async def test_release_raises_if_not_found(self):
        svc, ver_repo, _, _ = _make_service()
        ver_repo.get_by_vid = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.release("VID-999", "admin-1")


class TestFailRelease:
    async def test_fail_release_succeeds_with_valid_reason(self):
        svc, ver_repo, _, audit = _make_service()
        reason = "A" * 50  # exactly 50 chars
        with patch.object(svc, "_publish", AsyncMock()):
            result = await svc.fail_release("VID-001", "admin-1", reason)

        assert result.status == VerificationStatus.FAILED.value
        ver_repo.update.assert_called_once()
        audit.schedule.assert_called_once()

    async def test_fail_release_rejects_short_reason(self):
        svc, _, _, _ = _make_service()
        with pytest.raises(ValidationException, match="50 characters"):
            await svc.fail_release("VID-001", "admin-1", "Too short")

    async def test_fail_release_raises_if_not_under_review(self):
        svc, _, _, _ = _make_service(ver=_ver(status=VerificationStatus.COMPLETED.value))
        reason = "B" * 50
        with pytest.raises(Exception):
            await svc.fail_release("VID-001", "admin-1", reason)

    async def test_fail_release_audit_has_reason(self):
        svc, _, _, audit = _make_service()
        reason = "C" * 50
        with patch.object(svc, "_publish", AsyncMock()):
            await svc.fail_release("VID-001", "admin-1", reason)
        call_meta = audit.schedule.call_args.kwargs.get("details", {})
        assert call_meta.get("reason") == reason
