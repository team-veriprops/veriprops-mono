"""Unit tests for ConsentService public legal-document reads (S5). Seeding is done
by migration 0001 and guarded by test_migration_seed_parity.py."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.consent.models import (
    ConsentDocumentType,
    ConsentSignoffStatus,
)
from main.app.domain.user.auth.consent.service import ConsentService
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


def _make_svc(doc_repo=None):
    doc_repo = doc_repo or MagicMock()
    user_consent_repo = MagicMock()
    return ConsentService(doc_repo=doc_repo, user_consent_repo=user_consent_repo)


def _make_doc_row(doc_type, href, body="# body text long enough", status="DRAFT"):
    row = MagicMock()
    row.id = "doc-id"
    row.type = doc_type.value
    row.consent_version = "1.0.0"
    row.effective_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    row.title = "Title"
    row.href = href
    row.body = body
    row.signoff_status = status
    return row


class TestGetLegalDocument:
    async def test_returns_full_document_with_body(self):
        doc_repo = MagicMock()
        doc_repo.get_active_by_href = AsyncMock(
            return_value=_make_doc_row(ConsentDocumentType.PLATFORM_TERMS, "/legal/terms")
        )
        svc = _make_svc(doc_repo)

        dto = await svc.get_legal_document("terms")

        doc_repo.get_active_by_href.assert_awaited_once_with("/legal/terms")
        assert dto is not None
        assert dto.type == ConsentDocumentType.PLATFORM_TERMS
        assert dto.body
        assert dto.signoff_status == ConsentSignoffStatus.DRAFT

    async def test_returns_none_for_unknown_slug(self):
        doc_repo = MagicMock()
        doc_repo.get_active_by_href = AsyncMock(return_value=None)
        svc = _make_svc(doc_repo)

        assert await svc.get_legal_document("nope") is None


class TestListLegalDocuments:
    async def test_returns_summaries_without_body(self):
        rows = [
            _make_doc_row(ConsentDocumentType.PLATFORM_TERMS, "/legal/terms"),
            _make_doc_row(ConsentDocumentType.PRIVACY_POLICY, "/legal/privacy"),
        ]
        doc_repo = MagicMock()
        doc_repo.list_active = AsyncMock(return_value=rows)
        svc = _make_svc(doc_repo)

        summaries = await svc.list_legal_documents()

        assert len(summaries) == 2
        assert {s.href for s in summaries} == {"/legal/terms", "/legal/privacy"}
        assert not hasattr(summaries[0], "body") or getattr(summaries[0], "body", None) is None
