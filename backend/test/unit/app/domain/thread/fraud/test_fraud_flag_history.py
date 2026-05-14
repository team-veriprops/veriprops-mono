"""Unit tests for FraudDetectionService history method — S57 (R19.5)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.thread.fraud.models import FraudReviewDecision
from main.app.domain.thread.fraud.service import FraudDetectionService
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


def _make_flag(reviewed=False, decision=None):
    flag = MagicMock()
    flag.id = "flag-uuid"
    flag.message_id = "msg-1"
    flag.message_body = "suspicious text"
    flag.matched_patterns = json.dumps(["off-platform"])
    flag.reviewed = reviewed
    flag.review_decision = decision
    flag.reviewer_id = "admin-1" if reviewed else None
    flag.reviewed_at = datetime(2026, 5, 1, tzinfo=timezone.utc) if reviewed else None
    flag.date_created = datetime(2026, 4, 30, tzinfo=timezone.utc)
    return flag


def _make_svc(list_all=None):
    flag_repo = MagicMock()
    flag_repo.list_all = list_all or AsyncMock(return_value=([], 0))
    flag_repo.list_pending = AsyncMock(return_value=[])
    flag_repo.create_return_model = AsyncMock()
    message_repo = MagicMock()
    return FraudDetectionService(flag_repo=flag_repo, message_repo=message_repo)


class TestListHistory:
    async def test_returns_unreviewed_flags(self):
        flags = [_make_flag(reviewed=False)]
        svc = _make_svc(list_all=AsyncMock(return_value=(flags, 1)))

        result = await svc.list_history(reviewed=False, page=0, page_size=20)

        assert result.total == 1
        assert result.items[0].reviewed is False
        assert result.items[0].review_decision is None

    async def test_returns_reviewed_flags_with_decision(self):
        flags = [_make_flag(reviewed=True, decision=FraudReviewDecision.APPROVED.value)]
        svc = _make_svc(list_all=AsyncMock(return_value=(flags, 1)))

        result = await svc.list_history(reviewed=True, page=0, page_size=20)

        assert result.items[0].reviewed is True
        assert result.items[0].review_decision == FraudReviewDecision.APPROVED

    async def test_date_range_filter_is_forwarded(self):
        date_from = datetime(2026, 4, 1, tzinfo=timezone.utc)
        date_to = datetime(2026, 5, 1, tzinfo=timezone.utc)
        list_all_mock = AsyncMock(return_value=([], 0))
        svc = _make_svc(list_all=list_all_mock)

        await svc.list_history(date_from=date_from, date_to=date_to, page=0, page_size=10)

        list_all_mock.assert_awaited_once()
        call_kwargs = list_all_mock.call_args.kwargs
        assert call_kwargs["date_from"] == date_from
        assert call_kwargs["date_to"] == date_to

    async def test_empty_result_returns_empty_page(self):
        svc = _make_svc(list_all=AsyncMock(return_value=([], 0)))

        result = await svc.list_history()

        assert result.total == 0
        assert result.items == []
