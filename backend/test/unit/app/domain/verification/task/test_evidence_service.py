"""EvidenceService (§4.5, §12.3): content-hash + server-stamped GPS/timestamp on
capture, stored via the storage facade. Repo + provider mocked, no DB/storage."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.core.evidence import compute_content_hash
from main.app.domain.verification.task.evidence.models import EvidenceKind
from main.app.domain.verification.task.evidence.service import EvidenceService
from main.appodus_utils.db.session import db_session_ctx

# The smallest valid PNG header — enough for magic-byte sniffing.
PNG_BYTES = bytes.fromhex("89504e470d0a1a0a0000000d49484452") + bytes(17)

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

    async def test_stores_the_object_under_the_type_its_bytes_prove(self):
        svc = _make_service()
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=PNG_BYTES, kind=EvidenceKind.PHOTO, mime_type="image/jpeg",
        )
        assert svc._provider_mock.upload.await_args.kwargs["content_type"] == "image/png"

    @pytest.mark.parametrize("claimed", ["text/html", "image/svg+xml", None])
    async def test_bytes_that_are_not_an_evidence_format_are_stored_as_a_download(self, claimed):
        """A claimed type never reaches S3: markup served inline from the bucket would run."""
        svc = _make_service()
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=b"<html><script>alert(1)</script></html>", kind=EvidenceKind.PHOTO, mime_type=claimed,
        )
        assert svc._provider_mock.upload.await_args.kwargs["content_type"] == "application/octet-stream"

    async def test_the_client_claim_is_still_recorded_on_the_row(self):
        svc = _make_service()
        await svc.capture(
            task_id="t-1", verification_id="v-1", agent_id="a-1",
            file_bytes=PNG_BYTES, kind=EvidenceKind.PHOTO, mime_type="image/jpeg",
        )
        assert svc._created["dto"].mime_type == "image/jpeg"


class TestPresignedUrl:
    async def test_read_urls_live_for_the_configured_lifetime(self):
        svc = _make_service()
        svc._provider_mock.get_presigned_url = AsyncMock(return_value="https://signed")
        item = MagicMock(storage_key="evidence/v-1/t-1/abc")

        await svc.presigned_url(item)

        assert svc._provider_mock.get_presigned_url.await_args.kwargs["expires_in_sec"] == (
            settings.AWS_S3_PRESIGNED_URL_EXPIRES
        )
