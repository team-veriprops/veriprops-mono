"""KYC orchestration for agent onboarding (PRD §3.1).

Runs the applicant's check through the active provider (liveness, then the photo-on-file
match for BVN and NIN; other government IDs go to a person) and persists the result.

Every application reaches a reviewer — a failed check included, since the reviewer writes the
reason — so the selfie and, for a passport, driver's licence or voter's card, a photo of the
document are kept in private, encrypted storage for a side-by-side comparison. A reviewer
reads them only through short-lived links, and erasure deletes them.
"""
from __future__ import annotations

import base64
import binascii
import uuid
from typing import Optional, Tuple

from kink import inject
from pydantic import SecretStr

from main.app.config.settings import settings
from main.app.domain.user.agent.kyc.models import (
    CreateKycRecordDto,
    KycRecord,
    KycReviewImagesDto,
    KycSubmissionDto,
)
from main.app.domain.user.agent.kyc.repo import KycRecordRepo
from main.appodus_utils import FileUtils, Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory
from main.appodus_utils.integrations.kyc.factory import KycProviderFactory
from main.appodus_utils.integrations.kyc.models import (
    AUTO_VERIFIABLE_ID_TYPES,
    BvnVerificationRequest,
    GovIdVerificationRequest,
    KycMethod,
    KycResultStatus,
    KycVerificationResult,
)

# The one format accepted: Dojah documents base64 JPEG, and the wizard always re-encodes to it.
_JPEG = "image/jpeg"


def _folder(user_id: str) -> str:
    """Where a user's KYC photos live: erasure deletes this whole folder."""
    return f"kyc/{user_id}/"


class _Image:
    """A decoded, validated photo: its base64 for the provider, its bytes for storage."""

    def __init__(self, b64: str, data: bytes, content_type: str):
        self.b64, self.data, self.content_type = b64, data, content_type


def _decode(image: Optional[SecretStr], what: str) -> _Image:
    raw = (image.get_secret_value() if image else "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        data = b""
    if not data or FileUtils.sniff_mime(data) != _JPEG:
        raise ValidationException(message=f"The {what} must be a JPEG photo.")
    if len(data) > settings.KYC_IMAGE_MAX_BYTES:
        raise ValidationException(message=f"The {what} is too large. Retake it and try again.")
    return _Image(raw, data, _JPEG)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class KycService:
    def __init__(
        self,
        kyc_factory: KycProviderFactory,
        kyc_repo: KycRecordRepo,
        storage_factory: DocumentStorageProviderFactory,
    ):
        self._kyc_factory = kyc_factory
        self._kyc_repo = kyc_repo
        self._storage_factory = storage_factory

    async def run_verification(
        self, user_id: str, first_name: str, last_name: str, submission: KycSubmissionDto
    ) -> KycRecord:
        selfie, document = self._images(submission)
        # Stored before the paid provider call, so a storage failure costs nothing. Should the
        # submission roll back after this, the photos stay under the user's folder, which
        # erasure deletes whole.
        folder = f"{_folder(user_id)}{uuid.uuid4().hex}"
        selfie_key = await self._store(f"{folder}/selfie", selfie, user_id)
        document_key = await self._store(f"{folder}/document", document, user_id) if document else None

        provider = self._kyc_factory.get_active_provider()
        result = await self._verify(provider, first_name, last_name, submission, selfie)

        verified_at = Utils.datetime_now() if result.status == KycResultStatus.VERIFIED else None
        return await self._kyc_repo.create_return_model(CreateKycRecordDto(
            user_id=user_id,
            provider=result.provider,
            method=result.method,
            status=result.status,
            provider_ref=result.provider_ref,
            score=result.score,
            summary=result.summary,
            verified_at=verified_at,
            id_type=submission.id_type.value if submission.method == KycMethod.GOV_ID and submission.id_type else None,
            selfie_key=selfie_key,
            document_key=document_key,
        ))

    async def get_latest(self, user_id: str) -> Optional[KycRecord]:
        return await self._kyc_repo.get_latest_for_user(user_id)

    async def review_images(self, record: KycRecord) -> KycReviewImagesDto:
        """Short-lived links to the images kept for the reviewer; None where none were kept."""
        return KycReviewImagesDto(
            selfie_url=await self._link(record.selfie_key),
            document_url=await self._link(record.document_key),
        )

    async def delete_images(self, user_id: str) -> int:
        """Delete every stored KYC photo of the user (erasure, §4.11), including any no record
        points at (an upload whose submission rolled back). Returns how many."""
        return await self._storage_factory.storage().delete_prefix(_folder(user_id), settings.AWS_S3_BUCKET)

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _images(submission: KycSubmissionDto) -> Tuple[_Image, Optional[_Image]]:
        """Validate the photos before any paid provider call."""
        selfie = _decode(submission.selfie_image, "selfie")
        needs_document = (
            submission.method == KycMethod.GOV_ID
            and submission.id_type is not None
            and submission.id_type not in AUTO_VERIFIABLE_ID_TYPES
        )
        if needs_document and submission.id_document_image is None:
            raise ValidationException(message="Add a photo of your ID document.")
        document = _decode(submission.id_document_image, "ID photo") if needs_document else None
        return selfie, document

    async def _store(self, key: str, image: _Image, user_id: str) -> str:
        await self._storage_factory.storage().upload(
            key=key, bucket=settings.AWS_S3_BUCKET, file_bytes=image.data,
            metadata={"user_id": user_id, "purpose": "kyc"}, encrypted=True, content_type=image.content_type,
        )
        return key

    async def _link(self, key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        return await self._storage_factory.storage().get_presigned_url(
            key, settings.AWS_S3_BUCKET, expires_in_sec=settings.KYC_IMAGE_LINK_SECONDS,
        )

    async def _verify(
        self, provider, first_name: str, last_name: str, submission: KycSubmissionDto, selfie: _Image,
    ) -> KycVerificationResult:
        selfie_image = SecretStr(selfie.b64)
        if submission.method == KycMethod.BVN:
            if not submission.bvn:
                raise ValidationException(message="BVN is required for BVN verification.")
            return await provider.verify_bvn(BvnVerificationRequest(
                bvn=submission.bvn, first_name=first_name, last_name=last_name, selfie_image=selfie_image,
            ))
        if not submission.id_type or not submission.id_number:
            raise ValidationException(message="ID type and number are required for ID verification.")
        return await provider.verify_id_document(GovIdVerificationRequest(
            id_type=submission.id_type, id_number=submission.id_number,
            first_name=first_name, last_name=last_name, selfie_image=selfie_image,
        ))
