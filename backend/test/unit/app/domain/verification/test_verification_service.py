"""Unit tests for VerificationService (R5.1, R5.3, R5.4, R5.14).

Covers:
- VID format (VP-YYYY-XXXXXX)
- create_or_resume_draft idempotency
- update_draft_step payload merge + guards
- select_tier pricing lock
- submit wizard — happy paths (LAND / BUILDING), consent gates, state transition
- transition — timestamp recording, invalid-state guard
- upload_document — happy path + ownership/draft guards
"""
from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from main.app.domain.verification.models import (
    ConsentRecordDto,
    DocumentUploadResponseDto,
    PropertyDocumentType,
    VerificationStatus,
    VerificationTier,
    WizardStepDto,
)
from main.app.domain.verification.service import VerificationService, _generate_vid
from main.app.domain.verification.validator import VerificationValidator
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)

_ALL_CONSENTS = [
    ConsentRecordDto(document_type="VERIFICATION_DISCLAIMER", consent_version="1.0"),
    ConsentRecordDto(document_type="FINDINGS_OPINION_ACK", consent_version="1.0"),
    ConsentRecordDto(document_type="JURISDICTION_PLATFORM_ONLY", consent_version="1.0"),
    ConsentRecordDto(document_type="COMMUNICATION_RECORDING", consent_version="1.0"),
    ConsentRecordDto(document_type="REFUND_POLICY", consent_version="1.0"),
]

_LAND_PAYLOAD = {
    "propertyType": "LAND",
    "state": "LAGOS",
    "addressLine": "123 Test Road",
    "details": {"size": "500sqm", "use": "residential"},
}

_BUILDING_PAYLOAD = {
    "propertyType": "BUILDING",
    "state": "ABUJA",
    "addressLine": "5 Capital Drive",
    "details": {"type": "residential", "floors": 2},
    "sellerInfo": {"name": "John Doe", "phone": "08012345678"},
}


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


def _make_verification(
    *,
    customer_id: str = "cust-001",
    verification_id: str = "verif-001",
    vid: str = "VP-2026-ABCDEF",
    status: VerificationStatus = VerificationStatus.DRAFT,
    draft_payload: dict | None = None,
    draft_step: int = 0,
    property_id: str | None = None,
    tier: VerificationTier = VerificationTier.STANDARD,
    pricing_snapshot: str | None = None,
    paid_at: datetime | None = None,
    completed_at: datetime | None = None,
):
    row = MagicMock()
    row.id = verification_id
    row.customer_id = customer_id
    row.vid = vid
    row.status = status.value
    row.tier = tier.value
    row.draft_payload = json.dumps(draft_payload) if draft_payload else None
    row.draft_step = draft_step
    row.property_id = property_id
    row.pricing_snapshot = pricing_snapshot
    row.submitted_at = None
    row.paid_at = paid_at
    row.completed_at = completed_at
    row.date_created = _NOW
    row.date_updated = None
    return row


def _make_property(property_id: str = "prop-001"):
    prop = MagicMock()
    prop.id = property_id
    prop.source = "MANUAL"
    prop.property_type = "LAND"
    prop.state = "LAGOS"
    prop.lga = None
    prop.address_line = "123 Test Road"
    prop.lat = None
    prop.lng = None
    prop.landmark_description = None
    prop.details = None
    prop.documents = []
    prop.seller_info = None
    return prop


def _make_service():
    repo = AsyncMock()
    property_repo = AsyncMock()
    validator = VerificationValidator()
    pricing_service = MagicMock()
    consent_service = AsyncMock()
    audit = MagicMock()
    storage_factory = MagicMock()
    storage_provider = AsyncMock()
    storage_factory.get_active_provider.return_value = storage_provider

    svc = VerificationService(
        repo=repo,
        property_repo=property_repo,
        validator=validator,
        pricing_service=pricing_service,
        consent_service=consent_service,
        audit=audit,
        storage_factory=storage_factory,
    )
    return svc, repo, property_repo, pricing_service, consent_service, audit, storage_provider


# ── VID format ────────────────────────────────────────────────────────────────


class TestVidFormat:
    def test_vid_matches_pattern(self):
        vid = _generate_vid()
        assert re.match(r"^VP-\d{4}-[0-9A-F]{6}$", vid), f"Unexpected VID: {vid}"

    def test_vid_includes_current_year(self):
        vid = _generate_vid()
        year = str(datetime.utcnow().year)
        assert f"VP-{year}-" in vid

    def test_vid_uniqueness(self):
        vids = {_generate_vid() for _ in range(20)}
        assert len(vids) == 20


# ── create_or_resume_draft ────────────────────────────────────────────────────


class TestCreateOrResumeDraft:
    @pytest.mark.asyncio
    async def test_creates_new_draft_when_none_exists(self):
        svc, repo, property_repo, *_ = _make_service()
        repo.get_active_draft_for_customer.return_value = None
        new_row = _make_verification()
        repo.get_by_vid.return_value = new_row
        property_repo.get_model.return_value = None

        result = await svc.create_or_resume_draft("cust-001")

        repo.create.assert_awaited_once()
        create_args = repo.create.call_args[0][0]
        assert re.match(r"^VP-\d{4}-[0-9A-F]{6}$", create_args.vid)
        assert create_args.customer_id == "cust-001"
        assert create_args.status == VerificationStatus.DRAFT

    @pytest.mark.asyncio
    async def test_resumes_existing_draft(self):
        svc, repo, property_repo, *_ = _make_service()
        existing = _make_verification(vid="VP-2026-EXIST1")
        repo.get_active_draft_for_customer.return_value = existing
        property_repo.get_model.return_value = None

        result = await svc.create_or_resume_draft("cust-001")

        repo.create.assert_not_awaited()
        assert result.vid == "VP-2026-EXIST1"


# ── update_draft_step ─────────────────────────────────────────────────────────


class TestUpdateDraftStep:
    @pytest.mark.asyncio
    async def test_merges_payload_into_existing_draft(self):
        svc, repo, property_repo, *_ = _make_service()
        existing = _make_verification(draft_payload={"propertyType": "LAND"}, draft_step=0)
        updated = _make_verification(draft_payload={"propertyType": "LAND", "state": "LAGOS"}, draft_step=1)
        repo.get_model.side_effect = [existing, updated]
        property_repo.get_model.return_value = None

        dto = WizardStepDto(step=1, payload={"state": "LAGOS"})
        await svc.update_draft_step("cust-001", "verif-001", dto)

        repo.update.assert_awaited_once()
        update_dto = repo.update.call_args[0][1]
        merged = json.loads(update_dto.draft_payload)
        assert merged["propertyType"] == "LAND"
        assert merged["state"] == "LAGOS"
        assert update_dto.draft_step == 1

    @pytest.mark.asyncio
    async def test_rejects_non_owner(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(customer_id="other-user")

        with pytest.raises(ValidationException):
            await svc.update_draft_step("cust-001", "verif-001", WizardStepDto(step=1, payload={}))

    @pytest.mark.asyncio
    async def test_rejects_non_draft_status(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(status=VerificationStatus.SUBMITTED)

        with pytest.raises(ValidationException):
            await svc.update_draft_step("cust-001", "verif-001", WizardStepDto(step=2, payload={}))

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = None

        with pytest.raises(ResourceNotFoundException):
            await svc.update_draft_step("cust-001", "verif-001", WizardStepDto(step=1, payload={}))


# ── select_tier ───────────────────────────────────────────────────────────────


class TestSelectTier:
    @pytest.mark.asyncio
    async def test_locks_pricing_snapshot(self):
        svc, repo, property_repo, pricing_service, *_ = _make_service()
        row = _make_verification()
        updated = _make_verification()
        repo.get_model.side_effect = [row, updated]
        property_repo.get_model.return_value = None

        snapshot = MagicMock()
        snapshot.model_dump_json.return_value = '{"tier":"PREMIUM"}'
        pricing_service.quote.return_value = snapshot
        pricing_service.lock.return_value = snapshot

        await svc.select_tier("cust-001", "verif-001", VerificationTier.PREMIUM, "NGN")

        pricing_service.quote.assert_called_once_with(VerificationTier.PREMIUM, "NGN")
        pricing_service.lock.assert_called_once_with(snapshot)
        repo.update.assert_awaited_once()
        update_dto = repo.update.call_args[0][1]
        assert update_dto.tier == VerificationTier.PREMIUM
        assert update_dto.pricing_snapshot is not None


# ── submit ────────────────────────────────────────────────────────────────────


class TestSubmit:
    @pytest.mark.asyncio
    async def test_submit_happy_path_land(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_LAND_PAYLOAD)
        prop = _make_property()
        prop.property_type = "LAND"
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-001")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        result = await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

        assert result.status == VerificationStatus.SUBMITTED
        property_repo.create_return_model.assert_awaited_once()
        assert consent_service.record_user_consent.await_count == 5
        audit.schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_happy_path_building_with_seller_info(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_BUILDING_PAYLOAD)
        prop = _make_property()
        prop.property_type = "BUILDING"
        prop.state = "ABUJA"
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-001")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        result = await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

        assert result.status == VerificationStatus.SUBMITTED
        create_dto = property_repo.create_return_model.call_args[0][0]
        assert json.loads(create_dto.seller_info)["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_submit_missing_consent_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(draft_payload=_LAND_PAYLOAD)
        partial = _ALL_CONSENTS[:3]  # only 3 of 5

        with pytest.raises(ValidationException, match="Missing required consents"):
            await svc.submit("cust-001", "verif-001", partial)

    @pytest.mark.asyncio
    async def test_submit_no_consents_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(draft_payload=_LAND_PAYLOAD)

        with pytest.raises(ValidationException):
            await svc.submit("cust-001", "verif-001", [])

    @pytest.mark.asyncio
    async def test_submit_missing_property_type_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(
            draft_payload={"state": "LAGOS"},  # no propertyType
        )

        with pytest.raises(ValidationException, match="Property type is required"):
            await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

    @pytest.mark.asyncio
    async def test_submit_missing_state_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(
            draft_payload={"propertyType": "LAND"},  # no state
        )

        with pytest.raises(ValidationException, match="Property state is required"):
            await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

    @pytest.mark.asyncio
    async def test_submit_non_draft_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(status=VerificationStatus.SUBMITTED)

        with pytest.raises(ValidationException):
            await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

    @pytest.mark.asyncio
    async def test_submit_materialises_property(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_LAND_PAYLOAD)
        prop = _make_property()
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-001")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

        property_repo.create_return_model.assert_awaited_once()
        create_dto = property_repo.create_return_model.call_args[0][0]
        assert create_dto.property_type.value == "LAND"
        assert create_dto.state == "LAGOS"

    @pytest.mark.asyncio
    async def test_submit_records_all_five_consents(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_LAND_PAYLOAD)
        prop = _make_property()
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-001")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        await svc.submit("cust-001", "verif-001", _ALL_CONSENTS, ip_address="1.2.3.4")

        assert consent_service.record_user_consent.await_count == 5
        recorded_types = {
            c.kwargs["document_type"].value
            for c in consent_service.record_user_consent.await_args_list
        }
        assert "VERIFICATION_DISCLAIMER" in recorded_types
        assert "REFUND_POLICY" in recorded_types

    @pytest.mark.asyncio
    async def test_submit_schedules_audit_log(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_LAND_PAYLOAD)
        prop = _make_property()
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-001")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

        audit.schedule.assert_called_once()
        kwargs = audit.schedule.call_args[1]
        assert kwargs["from_state"] == VerificationStatus.DRAFT.value
        assert kwargs["to_state"] == VerificationStatus.SUBMITTED.value

    @pytest.mark.asyncio
    async def test_submit_stores_property_id(self):
        svc, repo, property_repo, _, consent_service, audit, *_ = _make_service()
        row = _make_verification(draft_payload=_LAND_PAYLOAD)
        prop = _make_property("prop-xyz")
        submitted_row = _make_verification(status=VerificationStatus.SUBMITTED, property_id="prop-xyz")
        repo.get_model.side_effect = [row, submitted_row]
        property_repo.create_return_model.return_value = prop
        property_repo.get_model.return_value = None

        await svc.submit("cust-001", "verif-001", _ALL_CONSENTS)

        update_dto = repo.update.call_args[0][1]
        assert update_dto.property_id == "prop-xyz"
        assert update_dto.status == VerificationStatus.SUBMITTED


# ── transition ────────────────────────────────────────────────────────────────


class TestTransition:
    @pytest.mark.asyncio
    async def test_transition_paid_sets_paid_at(self):
        svc, repo, property_repo, *_ = _make_service()
        row = _make_verification(status=VerificationStatus.PAYMENT_PENDING)
        paid_row = _make_verification(status=VerificationStatus.PAID)
        repo.get_model.side_effect = [row, paid_row]
        property_repo.get_model.return_value = None

        await svc.transition("verif-001", VerificationStatus.PAID, actor_id="admin-1")

        update_dto = repo.update.call_args[0][1]
        assert update_dto.status == VerificationStatus.PAID
        assert update_dto.paid_at is not None

    @pytest.mark.asyncio
    async def test_transition_completed_sets_completed_at(self):
        svc, repo, property_repo, *_ = _make_service()
        row = _make_verification(status=VerificationStatus.UNDER_REVIEW)
        completed_row = _make_verification(status=VerificationStatus.COMPLETED)
        repo.get_model.side_effect = [row, completed_row]
        property_repo.get_model.return_value = None

        await svc.transition("verif-001", VerificationStatus.COMPLETED, actor_id="admin-1")

        update_dto = repo.update.call_args[0][1]
        assert update_dto.status == VerificationStatus.COMPLETED
        assert update_dto.completed_at is not None

    @pytest.mark.asyncio
    async def test_transition_invalid_state_raises(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(status=VerificationStatus.DRAFT)

        with pytest.raises(InvalidResourceStateException):
            await svc.transition("verif-001", VerificationStatus.COMPLETED)


# ── upload_document ───────────────────────────────────────────────────────────


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_upload_document_happy_path(self):
        svc, repo, *rest = _make_service()
        storage_provider = rest[-1]
        repo.get_model.return_value = _make_verification()
        storage_provider.upload.return_value = "https://s3.example.com/verifications/verif-001/documents/abc.pdf"

        result = await svc.upload_document(
            "cust-001", "verif-001", b"pdf bytes", "survey.pdf", "SURVEY_PLAN",
        )

        assert isinstance(result, DocumentUploadResponseDto)
        assert result.url.startswith("https://s3.example.com")
        assert result.document_type == PropertyDocumentType.SURVEY_PLAN
        storage_provider.upload.assert_awaited_once()
        call_kwargs = storage_provider.upload.call_args[1]
        assert call_kwargs["encrypted"] is True
        assert "verif-001" in call_kwargs["key"]
        assert call_kwargs["key"].endswith(".pdf")

    @pytest.mark.asyncio
    async def test_upload_document_rejects_non_owner(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(customer_id="other-user")

        with pytest.raises(ValidationException):
            await svc.upload_document("cust-001", "verif-001", b"bytes", "file.pdf", "OTHER")

    @pytest.mark.asyncio
    async def test_upload_document_rejects_non_draft(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = _make_verification(status=VerificationStatus.SUBMITTED)

        with pytest.raises(ValidationException):
            await svc.upload_document("cust-001", "verif-001", b"bytes", "file.pdf", "OTHER")

    @pytest.mark.asyncio
    async def test_upload_document_raises_when_not_found(self):
        svc, repo, *_ = _make_service()
        repo.get_model.return_value = None

        with pytest.raises(ResourceNotFoundException):
            await svc.upload_document("cust-001", "verif-001", b"bytes", "file.pdf", "OTHER")
