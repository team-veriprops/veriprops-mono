"""Unit tests for IdempotencyService (PRD §4.6).

Repo is mocked (no DB); the autouse db-session fixture satisfies @transactional.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.idempotency.models import IdempotencyStatus
from main.app.core.idempotency.service import IdempotencyService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceConflictException,
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


def _existing(
    *,
    key="k-1",
    status=IdempotencyStatus.COMPLETED.value,
    request_hash=None,
    resource_id="res-1",
    response_snapshot=None,
):
    return SimpleNamespace(
        id="idem-uuid-1",
        key=key,
        scope="verification.create",
        status=status,
        request_hash=request_hash,
        resource_id=resource_id,
        response_snapshot=response_snapshot,
    )


def _make_service(existing=None) -> IdempotencyService:
    repo = MagicMock()
    repo.get_by_key = AsyncMock(return_value=existing)
    repo.create_return_model = AsyncMock()
    repo.update_return_model = AsyncMock()
    svc = object.__new__(IdempotencyService)
    svc._idempotency_repo = repo
    return svc


# ── begin_or_replay ──────────────────────────────────────────────────────────


class TestBeginOrReplay:
    async def test_fresh_key_reserves_one_row(self):
        svc = _make_service(existing=None)
        outcome = await svc.begin_or_replay("new-key", "verification.create", request_hash="h1")
        assert outcome.is_replay is False
        assert outcome.resource_id is None
        svc._idempotency_repo.create_return_model.assert_called_once()

    async def test_existing_key_replays_without_creating(self):
        existing = _existing(resource_id="ver-99", response_snapshot={"vid": "VP-2026-ABCDEF"})
        svc = _make_service(existing=existing)
        outcome = await svc.begin_or_replay("k-1", "verification.create")
        assert outcome.is_replay is True
        assert outcome.resource_id == "ver-99"
        assert outcome.response_snapshot == {"vid": "VP-2026-ABCDEF"}
        svc._idempotency_repo.create_return_model.assert_not_called()

    async def test_same_request_hash_replays(self):
        svc = _make_service(existing=_existing(request_hash="h1"))
        outcome = await svc.begin_or_replay("k-1", "verification.create", request_hash="h1")
        assert outcome.is_replay is True

    async def test_request_hash_mismatch_conflicts(self):
        svc = _make_service(existing=_existing(request_hash="h1"))
        with pytest.raises(ResourceConflictException):
            await svc.begin_or_replay("k-1", "verification.create", request_hash="DIFFERENT")


# ── complete ───────────────────────────────────────────────────────────────


class TestComplete:
    async def test_marks_completed_with_result(self):
        existing = _existing(status=IdempotencyStatus.PENDING.value, resource_id=None)
        svc = _make_service(existing=existing)
        await svc.complete("k-1", resource_id="ver-99", response_snapshot={"vid": "VP-2026-ABCDEF"})

        args = svc._idempotency_repo.update_return_model.call_args
        assert args.args[0] == "idem-uuid-1"
        update_dto = args.args[1]
        assert update_dto.status == IdempotencyStatus.COMPLETED
        assert update_dto.resource_id == "ver-99"
        assert update_dto.response_snapshot == {"vid": "VP-2026-ABCDEF"}

    async def test_unknown_key_raises(self):
        svc = _make_service(existing=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.complete("ghost-key")


# ── claim (webhook dedup) ────────────────────────────────────────────────────


class TestClaim:
    async def test_first_delivery_claims(self):
        svc = _make_service(existing=None)
        assert await svc.claim("evt_123", "webhook.flutterwave") is True
        svc._idempotency_repo.create_return_model.assert_called_once()

    async def test_replayed_delivery_is_dropped(self):
        svc = _make_service(existing=_existing(key="evt_123"))
        assert await svc.claim("evt_123", "webhook.flutterwave") is False
        svc._idempotency_repo.create_return_model.assert_not_called()
