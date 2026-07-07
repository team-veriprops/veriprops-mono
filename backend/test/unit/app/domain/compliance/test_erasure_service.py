"""Unit tests for ErasureService — S23 (R19.1, §4.11, §18.1)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import ErasureRequestState
from main.app.domain.audit.models import AuditActionType
from main.app.domain.compliance.erasure import service as service_module
from main.app.domain.compliance.erasure.service import ErasureService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    IllegalStateTransitionException,
    InvalidResourceStateException,
    ResourceNotFoundException,
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


@pytest.fixture(autouse=True)
def _no_publish(monkeypatch):
    """Isolate the event bus — the erasure notification is exercised in the live e2e."""
    monkeypatch.setattr(service_module, "publish_domain_event", AsyncMock())


def _row(status=ErasureRequestState.PENDING, subject="user-9"):
    r = MagicMock()
    r.id = "erasure-1"
    r.status = status.value
    r.subject_user_id = subject
    return r


def _make_svc(*, get_open=None, get_model=None, create=None, pseudonymise_surfaces=None):
    repo = MagicMock()
    repo.get_open_for_user = get_open or AsyncMock(return_value=None)
    repo.get_model = get_model or AsyncMock(return_value=None)
    repo.create_return_model = create or AsyncMock(return_value=_row())
    repo.page_by_status = AsyncMock(return_value=([], 0))
    repo.list_for_user = AsyncMock(return_value=[])

    users = MagicMock()
    users.get_model = AsyncMock(return_value=MagicMock(id="user-9"))

    config = MagicMock()
    config.get_int = AsyncMock(return_value=30)

    pseudonymiser = MagicMock()
    pseudonymiser.token_for = MagicMock(return_value="erased-abc123")
    pseudonymiser.pseudonymise = AsyncMock(return_value=pseudonymise_surfaces or ["users", "audit_logs"])

    audit = MagicMock()
    audit.schedule = MagicMock()

    svc = ErasureService(
        erasure_repo=repo, user_repo=users, config_service=config,
        pseudonymiser=pseudonymiser, audit_service=audit,
    )
    return svc, repo, pseudonymiser, audit


class TestRequest:
    async def test_creates_pending_request_and_audits(self):
        svc, repo, _, audit = _make_svc()
        await svc.request("user-9", "user-9", reason="Please erase me")

        repo.create_return_model.assert_awaited_once()
        created = repo.create_return_model.call_args.args[0]
        assert created.status == ErasureRequestState.PENDING
        assert created.sla_due_at is not None  # SLA computed from config
        assert audit.schedule.call_args.kwargs["action"] == AuditActionType.DATA_ERASURE_REQUESTED

    async def test_blocks_duplicate_open_request(self):
        svc, _, _, _ = _make_svc(get_open=AsyncMock(return_value=_row()))
        with pytest.raises(InvalidResourceStateException):
            await svc.request("user-9", "user-9", reason=None)

    async def test_unknown_subject_raises(self):
        svc, _, _, _ = _make_svc()
        svc._users.get_model = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.request("ghost", "ghost", reason=None)


class TestApproveReject:
    async def test_approve_moves_pending_to_approved(self):
        row = _row(ErasureRequestState.PENDING)
        svc, _, _, audit = _make_svc(get_model=AsyncMock(return_value=row))
        result = await svc.approve("erasure-1", "admin-1")
        assert result.status == ErasureRequestState.APPROVED.value
        assert result.reviewed_by_user_id == "admin-1"
        assert audit.schedule.call_args.kwargs["action"] == AuditActionType.DATA_ERASURE_APPROVED

    async def test_reject_records_note(self):
        row = _row(ErasureRequestState.PENDING)
        svc, _, _, _ = _make_svc(get_model=AsyncMock(return_value=row))
        result = await svc.reject("erasure-1", "admin-1", note="Identity unverified")
        assert result.status == ErasureRequestState.REJECTED.value
        assert result.decision_note == "Identity unverified"

    async def test_cannot_approve_an_executed_request(self):
        row = _row(ErasureRequestState.EXECUTED)
        svc, _, _, _ = _make_svc(get_model=AsyncMock(return_value=row))
        with pytest.raises(IllegalStateTransitionException):
            await svc.approve("erasure-1", "admin-1")


class TestExecute:
    async def test_execute_pseudonymises_and_stamps_token(self):
        row = _row(ErasureRequestState.APPROVED)
        svc, _, pseudonymiser, audit = _make_svc(get_model=AsyncMock(return_value=row))
        result = await svc.execute("erasure-1", "admin-1")

        pseudonymiser.pseudonymise.assert_awaited_once_with("user-9", "erased-abc123")
        assert result.status == ErasureRequestState.EXECUTED.value
        assert result.pseudonym_token == "erased-abc123"
        assert result.executed_at is not None
        kwargs = audit.schedule.call_args.kwargs
        assert kwargs["action"] == AuditActionType.DATA_ERASURE_EXECUTED
        assert kwargs["details"]["surfaces"] == ["users", "audit_logs"]

    async def test_execute_is_idempotent(self):
        row = _row(ErasureRequestState.EXECUTED)
        svc, _, pseudonymiser, _ = _make_svc(get_model=AsyncMock(return_value=row))
        result = await svc.execute("erasure-1", "admin-1")
        assert result.status == ErasureRequestState.EXECUTED.value
        pseudonymiser.pseudonymise.assert_not_awaited()  # no re-scrub

    async def test_cannot_execute_a_pending_request(self):
        row = _row(ErasureRequestState.PENDING)
        svc, _, _, _ = _make_svc(get_model=AsyncMock(return_value=row))
        with pytest.raises(IllegalStateTransitionException):
            await svc.execute("erasure-1", "admin-1")
