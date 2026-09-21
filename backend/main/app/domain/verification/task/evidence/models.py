"""Task evidence domain (PRD §4.5, §12.3, §12.3).

Each piece of proof an agent captures for a task — a geotagged photo, a document
scan, a short video, a certificate of inspection. Two integrity controls attach at
receipt: a per-item SHA-256 **content hash** (§4.5 — makes post-submission alteration
detectable) and **server-set GPS + timestamp** (§12.3 — proof-of-presence the client
cannot forge). The binary lives in object storage behind the storage facade; the row
holds the key, hash and provenance. A child of the task domain.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, Float, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


class EvidenceKind(str, enum.Enum):
    """What the captured artefact is (drives per-role validation, §12.2)."""

    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    SIGNATURE = "SIGNATURE"
    CERTIFICATE = "CERTIFICATE"  # certificate of inspection / COI


# ─── ORM ──────────────────────────────────────────────────────────

class EvidenceItem(BaseEntity):
    __tablename__ = "task_evidence"

    task_id = Column(String(36), nullable=False, index=True)
    verification_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(36), nullable=False)
    kind = Column(String(16), nullable=False, default=EvidenceKind.PHOTO.value)

    storage_key = Column(String(512), nullable=False)
    storage_url = Column(String(1024), nullable=True)  # presigned/synthetic; regenerated on read
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)

    # §4.5 tamper-evidence: SHA-256 of the exact bytes received.
    content_sha256 = Column(String(64), nullable=False)
    # §12.3 proof-of-presence: set server-side at receipt, never trusted from the client.
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)
    captured_at = Column(UTCDateTime, nullable=True)
    uploaded_at = Column(UTCDateTime, nullable=False)

    __table_args__ = (
        Index("ix_task_evidence_task", "task_id"),
        Index("ix_task_evidence_verification", "verification_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateEvidenceDto(Object):
    task_id: str
    verification_id: str
    agent_id: str
    kind: EvidenceKind = EvidenceKind.PHOTO
    storage_key: str
    storage_url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    content_sha256: str
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    captured_at: Optional[datetime] = None
    uploaded_at: datetime


class UpdateEvidenceDto(Object):
    storage_url: Optional[str] = None


class SearchEvidenceDto(InternalPageRequest, BaseQueryDto):
    task_id: Optional[str] = None
    verification_id: Optional[str] = None
    kind: Optional[str] = None


class QueryEvidenceDto(BaseQueryDto):
    task_id: Optional[str] = None
    verification_id: Optional[str] = None
    agent_id: Optional[str] = None
    kind: Optional[str] = None


class EvidenceDto(Object):
    """Evidence item shown in the agent submission review + admin task review."""

    id: str
    task_id: str
    verification_id: str
    kind: EvidenceKind
    storage_url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    content_sha256: str
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    captured_at: Optional[datetime] = None
    uploaded_at: datetime
