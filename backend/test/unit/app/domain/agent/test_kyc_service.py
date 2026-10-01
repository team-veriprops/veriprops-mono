"""KycService — an applicant's identity check, and the photos a reviewer compares (PRD §3.1).

The selfie goes to the provider for liveness and the photo-on-file match. Every application
reaches a reviewer, a failed check included, so the selfie — and, for a passport, driver's
licence or voter's card, a photo of the document — is kept in private storage for the side-by-
side comparison. The images are only ever read through short-lived links, and erasure deletes
them.
"""
import base64
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from main.app.config.settings import settings
from main.app.domain.user.agent.kyc.models import KycSubmissionDto
from main.app.domain.user.agent.kyc.service import KycService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.kyc.models import (
    GovIdType,
    KycMethod,
    KycProvider,
    KycResultStatus,
    KycVerificationResult,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _b64(data: bytes) -> SecretStr:
    return SecretStr(base64.b64encode(data).decode())


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


def _service(status=KycResultStatus.VERIFIED):
    svc = object.__new__(KycService)
    provider = AsyncMock()
    result = KycVerificationResult(
        provider=KycProvider.STUB, method=KycMethod.BVN, status=status, provider_ref="STUB-BVN-1",
        score=96, summary="ok",
    )
    provider.verify_bvn = AsyncMock(return_value=result)
    provider.verify_id_document = AsyncMock(return_value=result.model_copy(update={"method": KycMethod.GOV_ID}))
    svc._kyc_factory = MagicMock()
    svc._kyc_factory.get_active_provider = MagicMock(return_value=provider)
    svc._kyc_repo = AsyncMock()
    svc._kyc_repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="k-1", **dto.model_dump()))
    svc._storage = AsyncMock()
    svc._storage.upload = AsyncMock(return_value="https://store/x")
    svc._storage.get_presigned_url = AsyncMock(side_effect=lambda key, bucket, expires_in_sec: f"https://signed/{key}")
    svc._storage_factory = MagicMock()
    svc._storage_factory.storage = MagicMock(return_value=svc._storage)
    return svc, provider


def _bvn(selfie=JPEG):
    return KycSubmissionDto(method=KycMethod.BVN, bvn="22222222222", selfie_image=_b64(selfie))


def _passport(document=JPEG):
    return KycSubmissionDto(
        method=KycMethod.GOV_ID, id_type=GovIdType.PASSPORT, id_number="A01234567",
        selfie_image=_b64(JPEG), id_document_image=None if document is None else _b64(document),
    )


class TestSubmission:
    async def test_the_provider_receives_the_selfie_as_sent(self):
        svc, provider = _service()
        dto = _bvn()

        await svc.run_verification("u-1", "Ada", "Obi", dto)

        sent = provider.verify_bvn.call_args.args[0]
        assert sent.selfie_image.get_secret_value() == dto.selfie_image.get_secret_value()

    async def test_a_data_url_prefix_is_accepted_and_stripped(self):
        svc, provider = _service()
        dto = KycSubmissionDto(
            method=KycMethod.BVN, bvn="22222222222",
            selfie_image=SecretStr("data:image/jpeg;base64," + base64.b64encode(JPEG).decode()),
        )

        await svc.run_verification("u-1", "Ada", "Obi", dto)

        assert not provider.verify_bvn.call_args.args[0].selfie_image.get_secret_value().startswith("data:")

    # JPEG only: it is the format Dojah documents, and the one the wizard always sends.
    @pytest.mark.parametrize("selfie", [SecretStr("not-base64!!"), _b64(b"GIF89a" + b"\x00" * 20), _b64(PNG), SecretStr("")])
    async def test_a_selfie_that_is_not_a_jpeg_is_refused_before_the_provider(self, selfie):
        svc, provider = _service()

        with pytest.raises(ValidationException):
            await svc.run_verification("u-1", "Ada", "Obi", KycSubmissionDto(
                method=KycMethod.BVN, bvn="22222222222", selfie_image=selfie,
            ))
        provider.verify_bvn.assert_not_called()

    async def test_an_oversized_image_is_refused(self, monkeypatch):
        monkeypatch.setattr(settings, "KYC_IMAGE_MAX_BYTES", 32)
        svc, provider = _service()

        with pytest.raises(ValidationException):
            await svc.run_verification("u-1", "Ada", "Obi", _bvn())
        provider.verify_bvn.assert_not_called()

    async def test_a_passport_needs_a_photo_of_the_document(self):
        svc, provider = _service()

        with pytest.raises(ValidationException):
            await svc.run_verification("u-1", "Ada", "Obi", _passport(document=None))
        provider.verify_id_document.assert_not_called()


class TestStoredImages:
    async def test_the_selfie_is_kept_privately_for_the_reviewer(self):
        svc, _ = _service(KycResultStatus.VERIFIED)

        record = await svc.run_verification("u-1", "Ada", "Obi", _bvn())

        upload = svc._storage.upload.call_args.kwargs
        assert upload["key"].startswith("kyc/u-1/") and upload["key"].endswith("/selfie")
        assert upload["encrypted"] is True
        assert upload["content_type"] == "image/jpeg"
        assert upload["file_bytes"] == JPEG
        assert record.selfie_key == upload["key"]
        assert record.document_key is None

    async def test_a_passport_keeps_the_document_photo_beside_the_selfie(self):
        svc, _ = _service(KycResultStatus.NEEDS_REVIEW)

        record = await svc.run_verification("u-1", "Ada", "Obi", _passport(document=JPEG))

        keys = [c.kwargs["key"] for c in svc._storage.upload.call_args_list]
        assert [k.rsplit("/", 1)[-1] for k in keys] == ["selfie", "document"]
        assert (record.selfie_key, record.document_key) == tuple(keys)
        assert record.id_type == GovIdType.PASSPORT.value

    async def test_the_photos_are_stored_before_the_paid_provider_call(self):
        svc, provider = _service()
        order = []
        svc._storage.upload = AsyncMock(side_effect=lambda **kw: order.append("store"))
        provider.verify_bvn = AsyncMock(side_effect=lambda req: order.append("dojah") or KycVerificationResult(
            provider=KycProvider.STUB, method=KycMethod.BVN, status=KycResultStatus.VERIFIED, provider_ref="r",
        ))

        await svc.run_verification("u-1", "Ada", "Obi", _bvn())

        assert order == ["store", "dojah"]

    async def test_a_storage_failure_costs_no_provider_call(self):
        svc, provider = _service()
        svc._storage.upload = AsyncMock(side_effect=IntegrationException("Could not store the document."))

        with pytest.raises(IntegrationException):
            await svc.run_verification("u-1", "Ada", "Obi", _bvn())
        provider.verify_bvn.assert_not_called()

    async def test_a_failed_check_keeps_the_selfie_for_the_reviewer_who_writes_the_reason(self):
        svc, _ = _service(KycResultStatus.FAILED)

        record = await svc.run_verification("u-1", "Ada", "Obi", _bvn())

        assert record.selfie_key is not None


class TestReviewAndErasure:
    async def test_a_reviewer_reads_the_images_through_short_lived_links(self):
        svc, _ = _service()
        record = SimpleNamespace(selfie_key="kyc/u-1/r/selfie", document_key="kyc/u-1/r/document")

        images = await svc.review_images(record)

        assert (images.selfie_url, images.document_url) == (
            "https://signed/kyc/u-1/r/selfie", "https://signed/kyc/u-1/r/document",
        )
        assert svc._storage.get_presigned_url.call_args.kwargs["expires_in_sec"] == settings.KYC_IMAGE_LINK_SECONDS

    async def test_a_record_without_images_has_no_links(self):
        svc, _ = _service()

        images = await svc.review_images(SimpleNamespace(selfie_key=None, document_key=None))

        assert (images.selfie_url, images.document_url) == (None, None)

    async def test_erasure_deletes_everything_under_the_subjects_folder(self):
        # By prefix, not by the rows' keys: a submission that rolled back after its upload left
        # photos no row points at, and erasure must reach those too.
        svc, _ = _service()
        svc._storage.delete_prefix = AsyncMock(return_value=3)

        deleted = await svc.delete_images("u-1")

        svc._storage.delete_prefix.assert_awaited_once_with("kyc/u-1/", settings.AWS_S3_BUCKET)
        assert deleted == 3
