"""Unit tests for EvidenceService — GPS validation, photo count enforcement.

Covers:
- is_in_nigeria() boundary checks
- upload() rejects photo without GPS
- upload() rejects GPS outside Nigeria bounding box
- upload() accepts valid photo with GPS inside Nigeria
- assert_min_gps_photos() raises when count < minimum
- assert_min_gps_photos() passes when count >= minimum
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.task.evidence.models import (
    EvidenceItem,
    EvidenceType,
    is_in_nigeria,
)
from main.app.domain.verification.task.evidence.service import (
    PHOTO_MIN_COUNT,
    EvidenceService,
)
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


# ── fixtures ──────────────────────────────────────────────────────────────────

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


def _make_evidence_item(task_id: str = "t-1", gps_lat: float = 6.5, gps_lng: float = 7.0) -> EvidenceItem:
    item = MagicMock(spec=EvidenceItem)
    item.id = "ev-1"
    item.task_id = task_id
    item.uploader_id = "agent-1"
    item.type = EvidenceType.PHOTO.value
    item.file_url = "https://storage.example.com/evidence/t-1/agent-1/photo.jpg"
    item.gps_lat = gps_lat
    item.gps_lng = gps_lng
    item.captured_at = datetime.now(timezone.utc)
    item.details = {}
    item.date_created = datetime.now(timezone.utc)
    return item


def _make_service(gps_count: int = 0, stored_item: EvidenceItem | None = None):
    repo = MagicMock()
    repo.create_return_model = AsyncMock(return_value=stored_item or _make_evidence_item())
    repo.list_for_task = AsyncMock(return_value=[])
    repo.count_gps_for_task = AsyncMock(return_value=gps_count)
    storage_factory = MagicMock()
    provider = MagicMock()
    provider.upload = AsyncMock(return_value="https://storage.example.com/evidence/t-1/agent-1/photo.jpg")
    storage_factory.get_provider = MagicMock(return_value=provider)
    return EvidenceService(repo=repo, storage_factory=storage_factory)


# ── is_in_nigeria() ───────────────────────────────────────────────────────────

class TestIsInNigeria:
    @pytest.mark.parametrize("lat,lng", [
        (6.5, 7.0),    # Lagos area
        (9.0, 7.5),    # Abuja area
        (4.0, 3.0),    # SW corner
        (14.0, 15.0),  # NE corner
    ])
    def test_valid_nigeria_coordinates(self, lat, lng):
        assert is_in_nigeria(lat, lng) is True

    @pytest.mark.parametrize("lat,lng", [
        (3.9, 7.0),    # just south of lower bound
        (14.1, 7.0),   # just north of upper bound
        (6.5, 2.9),    # just west of left bound
        (6.5, 15.1),   # just east of right bound
        (0.0, 0.0),    # origin (Atlantic)
        (51.5, -0.1),  # London
        (-1.0, 36.8),  # Nairobi
    ])
    def test_outside_nigeria(self, lat, lng):
        assert is_in_nigeria(lat, lng) is False


# ── upload() GPS validation ───────────────────────────────────────────────────

class TestUpload:
    async def test_photo_without_gps_raises(self):
        svc = _make_service()
        with pytest.raises(ValidationException, match="GPS coordinates are required"):
            await svc.upload(
                task_id="t-1",
                uploader_id="a-1",
                file_bytes=b"data",
                filename="photo.jpg",
                evidence_type=EvidenceType.PHOTO,
                gps_lat=None,
                gps_lng=None,
            )

    async def test_photo_missing_lat_raises(self):
        svc = _make_service()
        with pytest.raises(ValidationException, match="GPS coordinates are required"):
            await svc.upload(
                task_id="t-1",
                uploader_id="a-1",
                file_bytes=b"data",
                filename="photo.jpg",
                evidence_type=EvidenceType.PHOTO,
                gps_lat=None,
                gps_lng=7.0,
            )

    async def test_photo_outside_nigeria_raises(self):
        svc = _make_service()
        with pytest.raises(ValidationException, match="within Nigeria"):
            await svc.upload(
                task_id="t-1",
                uploader_id="a-1",
                file_bytes=b"data",
                filename="photo.jpg",
                evidence_type=EvidenceType.PHOTO,
                gps_lat=51.5,   # London
                gps_lng=-0.1,
            )

    async def test_valid_gps_photo_succeeds(self):
        item = _make_evidence_item(gps_lat=6.5, gps_lng=7.0)
        svc = _make_service(stored_item=item)
        result = await svc.upload(
            task_id="t-1",
            uploader_id="a-1",
            file_bytes=b"data",
            filename="photo.jpg",
            evidence_type=EvidenceType.PHOTO,
            gps_lat=6.5,
            gps_lng=7.0,
        )
        assert result.gps_lat == 6.5
        assert result.gps_lng == 7.0

    async def test_document_upload_no_gps_required(self):
        """Documents don't need GPS coordinates."""
        svc = _make_service()
        # Should not raise even without GPS
        await svc.upload(
            task_id="t-1",
            uploader_id="a-1",
            file_bytes=b"data",
            filename="doc.pdf",
            evidence_type=EvidenceType.DOCUMENT,
            gps_lat=None,
            gps_lng=None,
        )


# ── assert_min_gps_photos() ───────────────────────────────────────────────────

class TestAssertMinGpsPhotos:
    async def test_raises_when_count_below_minimum(self):
        svc = _make_service(gps_count=PHOTO_MIN_COUNT - 1)
        with pytest.raises(ValidationException, match=str(PHOTO_MIN_COUNT)):
            await svc.assert_min_gps_photos("t-1")

    async def test_passes_when_count_meets_minimum(self):
        svc = _make_service(gps_count=PHOTO_MIN_COUNT)
        await svc.assert_min_gps_photos("t-1")  # must not raise

    async def test_passes_when_count_exceeds_minimum(self):
        svc = _make_service(gps_count=PHOTO_MIN_COUNT + 3)
        await svc.assert_min_gps_photos("t-1")  # must not raise

    async def test_raises_zero_photos(self):
        svc = _make_service(gps_count=0)
        with pytest.raises(ValidationException):
            await svc.assert_min_gps_photos("t-1")

    def test_photo_min_count_constant_is_five(self):
        assert PHOTO_MIN_COUNT == 5
