"""Evidence upload service — GPS validation, photo count enforcement."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.task.evidence.models import (
    CreateEvidenceItemDto,
    EvidenceItem,
    EvidenceItemDto,
    EvidenceType,
    is_in_nigeria,
)
from main.app.domain.verification.task.evidence.repo import EvidenceItemRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]

PHOTO_MIN_COUNT = 5  # field agent must upload ≥5 GPS-stamped photos


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class EvidenceService:
    def __init__(
        self,
        repo: EvidenceItemRepo,
        storage_factory: DocumentStorageProviderFactory,
    ):
        self._repo = repo
        self._storage = storage_factory

    async def upload(
        self,
        task_id: str,
        uploader_id: str,
        file_bytes: bytes,
        filename: str,
        evidence_type: EvidenceType = EvidenceType.PHOTO,
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None,
        captured_at: Optional[datetime] = None,
    ) -> EvidenceItemDto:
        # GPS validation for photos
        if evidence_type == EvidenceType.PHOTO:
            if gps_lat is None or gps_lng is None:
                raise ValidationException(message="GPS coordinates are required for photo evidence")
            if not is_in_nigeria(gps_lat, gps_lng):
                raise ValidationException(
                    message="GPS coordinates must be within Nigeria (4–14°N, 3–15°E)"
                )

        storage = self._storage.get_provider()
        object_key = f"evidence/{task_id}/{uploader_id}/{filename}"
        file_url = await storage.upload(
            file_bytes=file_bytes,
            object_key=object_key,
            content_type="application/octet-stream",
        )

        item = await self._repo.create_return_model(
            CreateEvidenceItemDto(
                task_id=task_id,
                uploader_id=uploader_id,
                type=evidence_type,
                file_url=file_url,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
                captured_at=captured_at or datetime.now(timezone.utc),
            )
        )
        return self._to_dto(item)

    async def list_for_task(self, task_id: str) -> List[EvidenceItemDto]:
        items = await self._repo.list_for_task(task_id)
        return [self._to_dto(i) for i in items]

    async def assert_min_gps_photos(self, task_id: str, minimum: int = PHOTO_MIN_COUNT) -> None:
        count = await self._repo.count_gps_for_task(task_id)
        if count < minimum:
            raise ValidationException(
                message=f"At least {minimum} GPS-stamped photos are required (uploaded: {count})"
            )

    @staticmethod
    def _to_dto(item: EvidenceItem) -> EvidenceItemDto:
        return EvidenceItemDto(
            id=str(item.id),
            task_id=item.task_id,
            uploader_id=item.uploader_id,
            type=EvidenceType(item.type),
            file_url=item.file_url,
            gps_lat=item.gps_lat,
            gps_lng=item.gps_lng,
            captured_at=item.captured_at,
            details=dict(item.details or {}),
            date_created=item.date_created,
        )
