"""Unit tests for ConsentService download methods — S57 (R19.4)."""
from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.consent.service import ConsentService
from main.appodus_utils.db.models import Page
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


def _make_consent_row(doc_type="PLATFORM_TERMS", version="1.0.0", ip="1.2.3.4"):
    row = MagicMock()
    row.document_type = doc_type
    row.consent_version = version
    row.accepted_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    row.ip_address = ip
    row.device_fingerprint = "fp-abc"
    return row


def _make_svc(list_for_user=None):
    doc_repo = MagicMock()
    user_consent_repo = MagicMock()
    user_consent_repo.list_for_user = list_for_user or AsyncMock(return_value=([], 0))
    user_consent_repo.latest_for_user = AsyncMock(return_value=None)
    user_consent_repo.create = AsyncMock()
    return ConsentService(doc_repo=doc_repo, user_consent_repo=user_consent_repo)


class TestListForUser:
    async def test_it_returns_the_standard_page_shape(self):
        """The history is a Page[T] like every other list, so the screen pages it the same way."""
        rows = [_make_consent_row(), _make_consent_row(doc_type="PRIVACY_POLICY")]
        list_for_user = AsyncMock(return_value=(rows, 5))
        svc = _make_svc(list_for_user=list_for_user)

        result = await svc.list_for_user("user-1", page=1, page_size=2)

        assert isinstance(result, Page)
        assert (result.meta.page, result.meta.page_size, result.meta.total) == (1, 2, 5)
        assert result.meta.total_pages == 3
        assert [i.document_type for i in result.items] == ["PLATFORM_TERMS", "PRIVACY_POLICY"]
        list_for_user.assert_awaited_once_with(user_id="user-1", offset=2, limit=2)

    async def test_it_defaults_to_the_first_page_of_ten(self):
        list_for_user = AsyncMock(return_value=([], 0))
        svc = _make_svc(list_for_user=list_for_user)

        result = await svc.list_for_user("user-1")

        assert result.items == []
        assert (result.meta.page, result.meta.page_size, result.meta.total) == (0, 10, 0)
        list_for_user.assert_awaited_once_with(user_id="user-1", offset=0, limit=10)


class TestExportForUserCsv:
    async def test_csv_has_correct_headers_and_rows(self):
        rows = [_make_consent_row()]
        svc = _make_svc(list_for_user=AsyncMock(return_value=(rows, 1)))

        data = await svc.export_for_user_csv("user-1")

        assert isinstance(data, bytes)
        reader = csv.reader(io.StringIO(data.decode("utf-8")))
        header = next(reader)
        assert header == [
            "document_type", "consent_version", "accepted_at", "ip_address", "device_fingerprint"
        ]
        row = next(reader)
        assert row[0] == "PLATFORM_TERMS"
        assert row[1] == "1.0.0"
        assert "2026-01-15" in row[2]
        assert row[3] == "1.2.3.4"
        assert row[4] == "fp-abc"

    async def test_empty_export_returns_header_only(self):
        svc = _make_svc(list_for_user=AsyncMock(return_value=([], 0)))

        data = await svc.export_for_user_csv("user-1")

        reader = csv.reader(io.StringIO(data.decode("utf-8")))
        rows = list(reader)
        assert len(rows) == 1  # header only
        assert rows[0][0] == "document_type"
