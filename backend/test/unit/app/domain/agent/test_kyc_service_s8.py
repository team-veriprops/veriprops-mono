"""Unit tests for AgentApplicationService KYC integration (S8 — R3.2, R3.6).

Verifies:
- verify_bvn() creates a KycRecord on success and failure
- record_kyc_documents() calls submit_selfie() and creates PENDING KycRecord
- process_kyc_webhook() resolves PENDING → PASSED (high score)
- process_kyc_webhook() resolves PENDING → UNDER_REVIEW (low score)
- process_kyc_webhook() resolves PENDING → FAILED (status!=success)
- admin_review_kyc() transitions UNDER_REVIEW → PASSED
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.agent.kyc.models import (
    AdminKycDecision,
    AdminKycReviewDto,
    KycStatus,
    KycType,
)
from main.app.domain.user.agent.kyc.interface import BvnVerificationResult
from main.app.domain.user.agent.models import (
    AgentApplicationStatus,
    BvnVerifyDto,
    IdDocType,
    KycDocumentsDto,
)
from main.appodus_utils.exception.exceptions import ValidationException

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


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


def _make_application(
    *,
    user_id: str = "user-001",
    app_id: str = "app-001",
    status: AgentApplicationStatus = AgentApplicationStatus.DRAFT,
    kyc_method: str | None = None,
    bvn_last4: str | None = None,
    id_doc_url: str | None = None,
    selfie_url: str | None = None,
):
    app = MagicMock()
    app.id = app_id
    app.user_id = user_id
    app.status = status.value
    app.types = ["FIELD"]
    app.kyc_method = kyc_method
    app.bvn_last4 = bvn_last4
    app.bvn_verification_id = None
    app.bvn_verified_at = None
    app.id_doc_url = id_doc_url
    app.selfie_url = selfie_url
    app.selfie_match_score = None
    app.selfie_matched_at = None
    app.id_doc_type = None
    app.surveyor_licence_no = None
    app.surveyor_licence_url = None
    app.nba_licence_no = None
    app.nba_licence_url = None
    app.years_of_experience = None
    app.coverage_states = ["LAGOS"]
    app.coverage_lgas = []
    app.bio = None
    app.submitted_at = None
    app.reviewed_at = None
    app.rejection_reason = None
    app.date_created = _NOW
    app.date_updated = None
    return app


def _make_kyc_record(
    *,
    record_id: str = "kyc-001",
    application_id: str = "app-001",
    user_id: str = "user-001",
    kyc_type: KycType = KycType.SELFIE_MATCH,
    status: KycStatus = KycStatus.PENDING,
    provider_ref: str = "selfie-job-xyz",
    score: int | None = None,
    admin_decision: str | None = None,
):
    r = MagicMock()
    r.id = record_id
    r.application_id = application_id
    r.user_id = user_id
    r.kyc_type = kyc_type.value
    r.status = status.value
    r.provider = "dojah"
    r.provider_ref = provider_ref
    r.score = score
    r.failure_reason = None
    r.webhook_payload = None
    r.reviewed_by_admin_id = None
    r.reviewed_at = None
    r.admin_decision = admin_decision
    r.admin_notes = None
    r.date_created = _NOW
    r.date_updated = None
    return r


def _make_service():
    from main.app.domain.user.agent.service import AgentApplicationService
    svc = object.__new__(AgentApplicationService)
    svc._repo = AsyncMock()
    svc._validator = MagicMock(unsafe=True)
    svc._consent_service = AsyncMock()
    svc._user_service = AsyncMock()
    svc._session_service = AsyncMock()
    svc._kyc = AsyncMock()
    svc._kyc_repo = AsyncMock()
    svc._audit = MagicMock()
    return svc


# ── verify_bvn() ─────────────────────────────────────────────────


async def test_verify_bvn_success_creates_passed_kyc_record():
    svc = _make_service()
    app = _make_application()
    updated = _make_application(kyc_method="BVN", bvn_last4="2222")

    svc._repo.get_by_user_id = AsyncMock(side_effect=[app, updated])
    svc._repo.update = AsyncMock()
    svc._kyc.verify_bvn = AsyncMock(return_value=BvnVerificationResult(
        verified=True, verification_id="dj-ref-001", provider="dojah",
    ))
    svc._kyc_repo.create = AsyncMock()

    with patch("main.app.domain.user.agent.service.settings") as mock_settings:
        mock_settings.KYC_SELFIE_REVIEW_THRESHOLD = 80
        result = await svc.verify_bvn("user-001", BvnVerifyDto(bvn="22222222222"))

    assert result.verified is True
    create_call = svc._kyc_repo.create.call_args[0][0]
    assert create_call.kyc_type == KycType.BVN_VERIFICATION
    assert create_call.status == KycStatus.PASSED
    assert create_call.provider == "dojah"


async def test_verify_bvn_failure_creates_failed_kyc_record():
    svc = _make_service()
    app = _make_application()

    svc._repo.get_by_user_id = AsyncMock(return_value=app)
    svc._kyc.verify_bvn = AsyncMock(return_value=BvnVerificationResult(
        verified=False, verification_id=None, failure_reason="Not found", provider="dojah",
    ))
    svc._kyc_repo.create = AsyncMock()

    result = await svc.verify_bvn("user-001", BvnVerifyDto(bvn="11111111111"))

    assert result.verified is False
    create_call = svc._kyc_repo.create.call_args[0][0]
    assert create_call.status == KycStatus.FAILED
    assert create_call.failure_reason == "Not found"


# ── record_kyc_documents() ────────────────────────────────────────


async def test_record_kyc_documents_creates_pending_selfie_record():
    svc = _make_service()
    app = _make_application()
    updated = _make_application(id_doc_url="s3://id-doc", selfie_url="s3://selfie")

    svc._repo.get_by_user_id = AsyncMock(side_effect=[app, updated])
    svc._repo.update = AsyncMock()
    svc._kyc.submit_selfie = AsyncMock(return_value="selfie-job-xyz")
    svc._kyc_repo.create = AsyncMock()

    await svc.record_kyc_documents(
        "user-001",
        KycDocumentsDto(id_doc_type=IdDocType.NIN, id_doc_url="s3://id-doc", selfie_url="s3://selfie"),
    )

    svc._kyc.submit_selfie.assert_called_once()
    create_call = svc._kyc_repo.create.call_args[0][0]
    assert create_call.kyc_type == KycType.SELFIE_MATCH
    assert create_call.status == KycStatus.PENDING
    assert create_call.provider_ref == "selfie-job-xyz"


# ── process_kyc_webhook() ─────────────────────────────────────────


async def test_process_webhook_high_score_resolves_to_passed():
    svc = _make_service()
    record = _make_kyc_record(status=KycStatus.PENDING, provider_ref="vf-001")

    svc._kyc_repo.get_by_provider_ref = AsyncMock(return_value=record)
    svc._kyc_repo.update = AsyncMock()

    payload = {"entity": {"verification_id": "vf-001", "status": "success", "confidence_score": 90}}

    with patch("main.app.domain.user.agent.service.settings") as mock_settings:
        mock_settings.KYC_SELFIE_REVIEW_THRESHOLD = 80
        await svc.process_kyc_webhook(payload)

    update_call = svc._kyc_repo.update.call_args[0][1]
    assert update_call.status == KycStatus.PASSED
    assert update_call.score == 90


async def test_process_webhook_low_score_resolves_to_under_review():
    svc = _make_service()
    record = _make_kyc_record(status=KycStatus.PENDING, provider_ref="vf-002")

    svc._kyc_repo.get_by_provider_ref = AsyncMock(return_value=record)
    svc._kyc_repo.update = AsyncMock()

    payload = {"entity": {"verification_id": "vf-002", "status": "success", "confidence_score": 70}}

    with patch("main.app.domain.user.agent.service.settings") as mock_settings:
        mock_settings.KYC_SELFIE_REVIEW_THRESHOLD = 80
        await svc.process_kyc_webhook(payload)

    update_call = svc._kyc_repo.update.call_args[0][1]
    assert update_call.status == KycStatus.UNDER_REVIEW
    assert update_call.score == 70


async def test_process_webhook_failed_status_resolves_to_failed():
    svc = _make_service()
    record = _make_kyc_record(status=KycStatus.PENDING, provider_ref="vf-003")

    svc._kyc_repo.get_by_provider_ref = AsyncMock(return_value=record)
    svc._kyc_repo.update = AsyncMock()

    payload = {"entity": {"verification_id": "vf-003", "status": "failed", "message": "No face"}}

    with patch("main.app.domain.user.agent.service.settings") as mock_settings:
        mock_settings.KYC_SELFIE_REVIEW_THRESHOLD = 80
        await svc.process_kyc_webhook(payload)

    update_call = svc._kyc_repo.update.call_args[0][1]
    assert update_call.status == KycStatus.FAILED


# ── admin_review_kyc() ────────────────────────────────────────────


async def test_admin_review_kyc_pass_transitions_to_passed():
    svc = _make_service()
    record = _make_kyc_record(status=KycStatus.UNDER_REVIEW, provider_ref="vf-004")
    resolved = _make_kyc_record(status=KycStatus.PASSED, admin_decision=AdminKycDecision.PASS.value)

    svc._kyc_repo.get_model = AsyncMock(side_effect=[record, resolved])
    svc._kyc_repo.update = AsyncMock()

    result = await svc.admin_review_kyc(
        "kyc-001", "admin-001", AdminKycReviewDto(decision=AdminKycDecision.PASS, notes="Looks good")
    )

    update_call = svc._kyc_repo.update.call_args[0][1]
    assert update_call.status == KycStatus.PASSED
    assert update_call.admin_decision == AdminKycDecision.PASS
    assert update_call.reviewed_by_admin_id == "admin-001"


async def test_admin_review_kyc_rejects_non_under_review_record():
    svc = _make_service()
    record = _make_kyc_record(status=KycStatus.PASSED)
    svc._kyc_repo.get_model = AsyncMock(return_value=record)

    with pytest.raises(ValidationException, match="UNDER_REVIEW"):
        await svc.admin_review_kyc(
            "kyc-001", "admin-001", AdminKycReviewDto(decision=AdminKycDecision.PASS)
        )
