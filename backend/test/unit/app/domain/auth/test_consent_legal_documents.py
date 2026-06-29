"""Unit tests for ConsentService legal-document seeding + public reads (S5)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
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


class TestSeedDocuments:
    async def test_inserts_all_documents_when_none_exist(self):
        doc_repo = MagicMock()
        doc_repo.get_by_type_version = AsyncMock(return_value=None)
        doc_repo.create = AsyncMock()
        doc_repo.update = AsyncMock()
        svc = _make_svc(doc_repo)

        await svc.seed_documents()

        assert doc_repo.create.await_count == len(LEGAL_DOCUMENT_CONTENT)
        assert doc_repo.update.await_count == 0
        # Body + signoff propagate into the create DTO.
        created = doc_repo.create.await_args_list[0].args[0]
        assert created.body
        assert created.signoff_status in (ConsentSignoffStatus.DRAFT, ConsentSignoffStatus.FINAL)

    async def test_updates_existing_documents_idempotently(self):
        doc_repo = MagicMock()
        doc_repo.get_by_type_version = AsyncMock(
            side_effect=lambda t, v: _make_doc_row(t, "/legal/x")
        )
        doc_repo.create = AsyncMock()
        doc_repo.update = AsyncMock()
        svc = _make_svc(doc_repo)

        await svc.seed_documents()

        assert doc_repo.update.await_count == len(LEGAL_DOCUMENT_CONTENT)
        assert doc_repo.create.await_count == 0


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
