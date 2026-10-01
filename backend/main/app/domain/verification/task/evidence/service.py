"""Task evidence service (PRD §4.5, §12.3).

Receives an agent's captured file, applies the two receipt-time integrity controls
— per-item SHA-256 content hash (§4.5) and server-set GPS + timestamp (§12.3) — uploads
the bytes through the storage facade (deterministic stub default, real S3/R2 by settings),
and persists the evidence row. The client-supplied GPS is accepted only as a hint; the
authoritative capture facts are stamped here so they cannot be forged.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.evidence import compute_content_hash
from main.app.domain.verification.task.evidence.models import (
    CreateEvidenceDto,
    EvidenceItem,
    EvidenceKind,
)
from main.app.domain.verification.task.evidence.repo import EvidenceRepo
from main.appodus_utils import FileUtils, Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory
from main.appodus_utils.integrations.document_storage.interface import IDocumentStorageProvider


# Formats the store may serve inline: the photos, video and documents an agent captures.
# Anything else (markup, SVG, scripts, unrecognised bytes) is stored as a download, because
# a presigned URL renders on the bucket's origin and inline markup there would run.
_INLINE_EVIDENCE_MIME_TYPES = frozenset({
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "application/pdf", "video/mp4", "video/quicktime",
})
_DOWNLOAD_CONTENT_TYPE = "application/octet-stream"


def _stored_content_type(file_bytes: bytes) -> str:
    """The Content-Type an evidence object is stored under: what its bytes prove, never the
    uploader's claim (which is still recorded on the evidence row as display metadata)."""
    mime = FileUtils.sniff_mime(file_bytes)
    return mime if mime in _INLINE_EVIDENCE_MIME_TYPES else _DOWNLOAD_CONTENT_TYPE


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class EvidenceService:
    def __init__(self, evidence_repo: EvidenceRepo, storage_factory: DocumentStorageProviderFactory):
        self._evidence_repo = evidence_repo
        self._storage_factory = storage_factory

    async def capture(
        self,
        *,
        task_id: str,
        verification_id: str,
        agent_id: str,
        file_bytes: bytes,
        kind: EvidenceKind,
        mime_type: Optional[str] = None,
        gps_latitude: Optional[float] = None,
        gps_longitude: Optional[float] = None,
        captured_at: Optional[datetime] = None,
    ) -> EvidenceItem:
        """Hash + stamp + store + persist a single evidence item. Encrypted at rest
        (server-side) via the storage facade; the row is the tamper-evident record."""
        content_hash = compute_content_hash(file_bytes)
        now = Utils.datetime_now()
        # Content-addressed key: dedupes identical bytes and ties the object to its hash.
        key = f"evidence/{verification_id}/{task_id}/{content_hash}"

        provider = self._provider()
        storage_url = await provider.upload(
            key=key,
            bucket=settings.AWS_S3_BUCKET,
            file_bytes=file_bytes,
            metadata={"task_id": task_id, "agent_id": agent_id, "sha256": content_hash},
            encrypted=True,
            content_type=_stored_content_type(file_bytes),
        )

        return await self._evidence_repo.create_return_model(CreateEvidenceDto(
            task_id=task_id,
            verification_id=verification_id,
            agent_id=agent_id,
            kind=kind,
            storage_key=key,
            storage_url=storage_url,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
            content_sha256=content_hash,
            gps_latitude=gps_latitude,
            gps_longitude=gps_longitude,
            captured_at=captured_at or now,
            uploaded_at=now,
        ))

    async def list_for_task(self, task_id: str) -> List[EvidenceItem]:
        return await self._evidence_repo.list_for_task(task_id)

    async def list_for_verification(self, verification_id: str) -> List[EvidenceItem]:
        """All evidence for a verification, newest first — feeds the customer feed (§9.4)."""
        return await self._evidence_repo.list_for_verification(verification_id)

    async def count_for_task(self, task_id: str) -> int:
        return await self._evidence_repo.count_for_task(task_id)

    async def presigned_url(self, item: EvidenceItem) -> str:
        """Fresh short-lived read URL for an evidence object (regenerated per read).

        Routes through the same provider selection as capture, so the deterministic stub
        serves a stable synthetic URL with no bucket/creds in tests/local."""
        provider = self._provider()
        return await provider.get_presigned_url(
            item.storage_key, settings.AWS_S3_BUCKET, expires_in_sec=settings.AWS_S3_PRESIGNED_URL_EXPIRES
        )

    def _provider(self) -> IDocumentStorageProvider:
        return self._storage_factory.storage()
