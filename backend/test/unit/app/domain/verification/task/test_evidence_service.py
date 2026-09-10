"""EvidenceService (§4.5, §12.3): content-hash + server-stamped GPS/timestamp on
capture, stored via the storage facade. Repo + provider mocked, no DB/storage."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.evidence import compute_content_hash
from main.app.domain.verification.task.evidence.models import EvidenceKind
from main.app.domain.verification.task.evidence.service import EvidenceService
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


def _make_service():
    svc = object.__new__(EvidenceService)
    svc._evidence_repo = MagicMock()
    svc._storage_factory = MagicMock()

    created = {}

    async def _create(dto):
        created["dto"] = dto
        return MagicMock(id="ev-1", content_sha256=dto.content_sha256, kind=dto.kind.value)

    svc._evidence_repo.create_return_model = AsyncMock(side_effect=_create)

    provider = MagicMock()
    provider.upload = AsyncMock(return_value="stub-storage://bucket/key")
    svc._provider = MagicMock(return_value=provider)
    svc._created = created
    svc._provider_mock = provider
    return svc


class TestCapture:
    async def test_computes_content_hash(self):
        svc = _make_service()
        data = b"proof-bytes"
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=data, kind=EvidenceKind.PHOTO,
        )
        assert svc._created["dto"].content_sha256 == compute_content_hash(data)

    async def test_stamps_uploaded_at_and_size(self):
        svc = _make_service()
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=b"abc", kind=EvidenceKind.DOCUMENT,
        )
        dto = svc._created["dto"]
        assert dto.uploaded_at is not None
        assert dto.size_bytes == 3

    async def test_uploads_encrypted_via_facade(self):
        svc = _make_service()
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=b"abc", kind=EvidenceKind.PHOTO,
        )
        assert svc._provider_mock.upload.await_args.kwargs["encrypted"] is True
