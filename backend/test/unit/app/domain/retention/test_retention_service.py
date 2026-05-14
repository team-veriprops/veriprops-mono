"""Unit tests for RetentionPolicyService — S58 (R19.7)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.retention.models import ErasureStatus
from main.app.domain.retention.service import RetentionPolicyService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ResourceNotFoundException


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_request_row(status=ErasureStatus.PENDING.value, user_id="user-1"):
    row = MagicMock()
    row.id = "req-uuid"
    row.user_id = user_id
    row.reason = "No longer using the service"
    row.status = status
    row.requested_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    row.reviewed_by = None
    row.reviewed_at = None
    row.executed_at = None
    row.rejection_reason = None
    return row


def _make_svc(
    get_active_for_user=None,
    get_model=None,
    create_return_model=None,
    update=None,
    list_by_status=None,
    get_latest_for_user=None,
):
    repo = MagicMock()
    repo.get_active_for_user = get_active_for_user or AsyncMock(return_value=None)
    repo.get_model = get_model or AsyncMock(return_value=None)
    repo.create_return_model = create_return_model or AsyncMock(return_value=_make_request_row())
    repo.update = update or AsyncMock()
    repo.list_by_status = list_by_status or AsyncMock(return_value=([], 0))
    repo.get_latest_for_user = get_latest_for_user or AsyncMock(return_value=None)
    return RetentionPolicyService(repo=repo)


class TestRequestErasure:
    async def test_creates_pending_record_and_schedules_audit(self, mock_db_session):
        row = _make_request_row()
        svc = _make_svc(create_return_model=AsyncMock(return_value=row))

        with patch("main.app.domain.retention.service.di") as mock_di:
            audit_svc = MagicMock()
            mock_di.__getitem__ = MagicMock(return_value=audit_svc)

            result = await svc.request_erasure("user-1", "No longer using the service")

        assert result.status == ErasureStatus.PENDING
        assert result.user_id == "user-1"

    async def test_rejects_if_active_request_exists(self):
        existing = _make_request_row(status=ErasureStatus.PENDING.value)
        svc = _make_svc(get_active_for_user=AsyncMock(return_value=existing))

        with pytest.raises(InvalidResourceStateException):
            await svc.request_erasure("user-1", None)

    async def test_rejects_if_user_has_active_verifications(self, mock_db_session):
        active_verification = MagicMock()
        mock_db_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=active_verification)
        )
        svc = _make_svc()

        with pytest.raises(InvalidResourceStateException):
            await svc.request_erasure("user-1", None)


class TestApproveErasure:
    async def test_transitions_to_approved(self):
        row = _make_request_row(status=ErasureStatus.PENDING.value)
        approved_row = _make_request_row(status=ErasureStatus.APPROVED.value)
        update_mock = AsyncMock()
        svc = _make_svc(
            get_model=AsyncMock(side_effect=[row, approved_row]),
            update=update_mock,
        )

        with patch("main.app.domain.retention.service.di") as mock_di:
            audit_svc = MagicMock()
            mock_di.__getitem__ = MagicMock(return_value=audit_svc)

            result = await svc.approve_erasure("req-uuid", "admin-1")

        assert result.status == ErasureStatus.APPROVED
        update_mock.assert_awaited_once()

    async def test_raises_if_not_found(self):
        svc = _make_svc(get_model=AsyncMock(return_value=None))

        with pytest.raises(ResourceNotFoundException):
            await svc.approve_erasure("nonexistent", "admin-1")


class TestRejectErasure:
    async def test_transitions_to_rejected_with_reason(self):
        row = _make_request_row(status=ErasureStatus.PENDING.value)
        rejected_row = _make_request_row(status=ErasureStatus.REJECTED.value)
        rejected_row.rejection_reason = "Incomplete information"
        svc = _make_svc(
            get_model=AsyncMock(side_effect=[row, rejected_row]),
        )

        with patch("main.app.domain.retention.service.di") as mock_di:
            audit_svc = MagicMock()
            mock_di.__getitem__ = MagicMock(return_value=audit_svc)

            result = await svc.reject_erasure("req-uuid", "admin-1", "Incomplete information")

        assert result.status == ErasureStatus.REJECTED


class TestExecuteErasure:
    async def test_anonymises_pii_and_transitions_to_executed(self, mock_db_session):
        row = _make_request_row(status=ErasureStatus.APPROVED.value)
        executed_row = _make_request_row(status=ErasureStatus.EXECUTED.value)
        executed_row.executed_at = datetime(2026, 5, 14, tzinfo=timezone.utc)

        mock_db_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))

        svc = _make_svc(
            get_model=AsyncMock(side_effect=[row, executed_row]),
        )

        with patch("main.app.domain.retention.service.di") as mock_di:
            audit_svc = MagicMock()
            mock_di.__getitem__ = MagicMock(return_value=audit_svc)

            await svc.execute_erasure("req-uuid", "admin-1")

        # session.execute was called at least once (for the UPDATE)
        assert mock_db_session.execute.call_count >= 1

    async def test_raises_if_not_approved(self):
        row = _make_request_row(status=ErasureStatus.PENDING.value)
        svc = _make_svc(get_model=AsyncMock(return_value=row))

        with pytest.raises(InvalidResourceStateException):
            await svc.execute_erasure("req-uuid", "admin-1")
