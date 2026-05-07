"""Unit tests for the agent application wizard (R3.1, R3.3, R3.4, R3.7).

Verifies:
- R3.1  Type selection: multi-select persisted; empty list rejected; immutability enforced.
- R3.3  Conditional credentials: SURVEYOR requires licence; LAWYER requires NBA; FIELD needs neither.
- R3.4  Versioned consent: record_user_consent called with AGENT_TERMS on submit.
- R3.7  Resumable wizard: get_or_create_for_user is idempotent; wizard state preserved.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.agent.models import (
    AgentApplicationStatus,
    AgentType,
    CredentialsStepDto,
    SubmitApplicationDto,
    TypesStepDto,
)
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


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


def _make_application(
    *,
    user_id: str = "user-001",
    app_id: str = "app-001",
    status: AgentApplicationStatus = AgentApplicationStatus.DRAFT,
    types: list | None = None,
    kyc_method: str | None = "BVN",
    bvn_verification_id: str | None = "bvn-verify-id",
    coverage_states: list | None = None,
    rejection_reason: str | None = None,
):
    app = MagicMock()
    app.id = app_id
    app.user_id = user_id
    app.status = status.value
    app.types = types if types is not None else ["FIELD"]
    app.kyc_method = kyc_method
    app.bvn_verification_id = bvn_verification_id
    app.bvn_last4 = "1234"
    app.bvn_verified_at = None
    app.id_doc_url = None
    app.selfie_url = None
    app.selfie_match_score = None
    app.selfie_matched_at = None
    app.id_doc_type = None
    app.surveyor_licence_no = None
    app.surveyor_licence_url = None
    app.nba_licence_no = None
    app.nba_licence_url = None
    app.years_of_experience = None
    app.coverage_states = coverage_states if coverage_states is not None else ["LAGOS"]
    app.coverage_lgas = []
    app.bio = None
    app.submitted_at = None
    app.reviewed_at = None
    app.rejection_reason = rejection_reason
    app.date_created = _NOW
    app.date_updated = None
    return app


def _make_service():
    from main.app.domain.user.agent.service import AgentApplicationService
    svc = object.__new__(AgentApplicationService)
    svc._repo = AsyncMock()
    svc._validator = MagicMock(unsafe=True)  # validator methods all start with assert_
    svc._consent_service = AsyncMock()
    svc._user_service = AsyncMock()
    svc._session_service = AsyncMock()
    svc._kyc = AsyncMock()
    svc._audit = MagicMock()
    return svc


# ── R3.7: Resumable wizard ────────────────────────────────────────────────────


async def test_get_or_create_creates_draft_on_first_call():
    """First call creates a DRAFT row when none exists (R3.7)."""
    svc = _make_service()
    svc._repo.get_by_user_id = AsyncMock(side_effect=[None, _make_application()])
    svc._repo.create = AsyncMock()

    result = await svc.get_or_create_for_user("user-001")

    svc._repo.create.assert_called_once()
    assert result.status == AgentApplicationStatus.DRAFT


async def test_get_or_create_idempotent():
    """Second call returns the existing row without calling create (R3.7)."""
    existing = _make_application()
    svc = _make_service()
    svc._repo.get_by_user_id = AsyncMock(return_value=existing)

    result = await svc.get_or_create_for_user("user-001")

    svc._repo.create.assert_not_called()
    assert result.user_id == "user-001"


async def test_draft_resume_preserves_wizard_state():
    """get_or_create_for_user returns existing row with previously saved types (R3.7)."""
    existing = _make_application(types=["SURVEYOR", "FIELD"])
    svc = _make_service()
    svc._repo.get_by_user_id = AsyncMock(return_value=existing)

    result = await svc.get_or_create_for_user("user-001")

    assert AgentType.SURVEYOR in result.types
    assert AgentType.FIELD in result.types


# ── R3.1: Type selection ──────────────────────────────────────────────────────


async def test_update_types_persists_multi_select():
    """FIELD + SURVEYOR types are saved to the repo (R3.1)."""
    app = _make_application()
    updated = _make_application(types=["FIELD", "SURVEYOR"])
    svc = _make_service()
    # get_or_create_for_user calls get_by_user_id once, then update_types calls it twice more
    svc._repo.get_by_user_id = AsyncMock(side_effect=[app, app, updated])
    svc._repo.create = AsyncMock()
    svc._repo.update = AsyncMock()

    result = await svc.update_types("user-001", TypesStepDto(types=[AgentType.FIELD, AgentType.SURVEYOR]))

    svc._repo.update.assert_called_once()
    update_dto = svc._repo.update.call_args[0][1]
    assert AgentType.FIELD in update_dto.types
    assert AgentType.SURVEYOR in update_dto.types
    assert AgentType.FIELD in result.types


async def test_update_types_rejects_empty_list():
    """Validator raises when types list is empty (R3.1)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    with pytest.raises(ValidationException):
        validator.assert_types([])


async def test_update_types_rejected_when_pending():
    """Validator raises when application is already PENDING (R3.1)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    pending_app = _make_application(status=AgentApplicationStatus.PENDING)
    validator = AgentApplicationValidator()
    with pytest.raises(InvalidResourceStateException):
        validator.assert_mutable(pending_app)


# ── R3.3: Conditional credentials ────────────────────────────────────────────


async def test_credentials_surveyor_requires_licence_no():
    """Missing surveyor_licence_no raises for SURVEYOR type (R3.3)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    dto = CredentialsStepDto(
        surveyor_licence_no=None,
        surveyor_licence_url=None,
        coverage_states=["LAGOS"],
        coverage_lgas=[],
    )
    with pytest.raises(ValidationException, match="Surveyor"):
        validator.assert_credentials(["SURVEYOR"], dto)


async def test_credentials_surveyor_requires_licence_url():
    """Missing surveyor_licence_url raises even when licence_no is present (R3.3)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    dto = CredentialsStepDto(
        surveyor_licence_no="SRV-001",
        surveyor_licence_url=None,
        coverage_states=["LAGOS"],
        coverage_lgas=[],
    )
    with pytest.raises(ValidationException, match="Surveyor"):
        validator.assert_credentials(["SURVEYOR"], dto)


async def test_credentials_lawyer_requires_nba_licence_no():
    """Missing nba_licence_no raises for LAWYER type (R3.3)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    dto = CredentialsStepDto(
        nba_licence_no=None,
        nba_licence_url=None,
        coverage_states=["LAGOS"],
        coverage_lgas=[],
    )
    with pytest.raises(ValidationException, match="NBA"):
        validator.assert_credentials(["LAWYER"], dto)


async def test_credentials_field_agent_no_licence_required():
    """FIELD type with no licence passes credential validation (R3.3)."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    dto = CredentialsStepDto(coverage_states=["LAGOS"], coverage_lgas=[])
    validator.assert_credentials(["FIELD"], dto)  # must not raise


# ── R3.4: Versioned consent ───────────────────────────────────────────────────


async def test_submit_calls_record_user_consent():
    """submit() records AGENT_TERMS consent with the version the applicant saw (R3.4)."""
    app = _make_application()
    submitted_app = _make_application(status=AgentApplicationStatus.PENDING)
    svc = _make_service()
    svc._repo.get_by_user_id = AsyncMock(side_effect=[app, submitted_app])
    svc._repo.update = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()

    await svc.submit(
        "user-001",
        SubmitApplicationDto(truthfulness_acknowledged=True, agent_terms_consent_version="1.0.0"),
        ip_address="10.0.0.1",
        device_fingerprint="fp-test",
    )

    svc._consent_service.record_user_consent.assert_awaited_once()
    call_args = svc._consent_service.record_user_consent.call_args
    # Accept both positional and keyword argument styles
    all_args = list(call_args.args) + list(call_args.kwargs.values())
    assert ConsentDocumentType.AGENT_TERMS in all_args
    assert "1.0.0" in all_args


async def test_submit_transitions_to_pending():
    """submit() transitions the application to PENDING status (R3.4)."""
    app = _make_application()
    pending_app = _make_application(status=AgentApplicationStatus.PENDING)
    svc = _make_service()
    svc._repo.get_by_user_id = AsyncMock(side_effect=[app, pending_app])
    svc._repo.update = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()

    result = await svc.submit(
        "user-001",
        SubmitApplicationDto(truthfulness_acknowledged=True, agent_terms_consent_version="1.0.0"),
    )

    svc._repo.update.assert_called_once()
    update_dto = svc._repo.update.call_args[0][1]
    assert update_dto.status == AgentApplicationStatus.PENDING
    assert result.status == AgentApplicationStatus.PENDING


async def test_submit_rejects_unacknowledged_truthfulness():
    """submit() raises ValidationException when truthfulness_acknowledged is False (R3.4)."""
    svc = _make_service()

    with pytest.raises(ValidationException, match="truthfulness"):
        await svc.submit(
            "user-001",
            SubmitApplicationDto(truthfulness_acknowledged=False, agent_terms_consent_version="1.0.0"),
        )

    svc._repo.get_by_user_id.assert_not_called()


# ── Admin actions ─────────────────────────────────────────────────────────────


async def test_approve_elevates_agent_persona():
    """approve() calls add_persona(AGENT) so the user gains the agent role."""
    pending_app = _make_application(status=AgentApplicationStatus.PENDING)
    approved_app = _make_application(status=AgentApplicationStatus.APPROVED)
    svc = _make_service()
    svc._repo.get_model = AsyncMock(side_effect=[pending_app, approved_app])
    svc._repo.update = AsyncMock()
    svc._user_service.add_persona = AsyncMock()

    await svc.approve("app-001", "admin-001")

    svc._user_service.add_persona.assert_awaited_once_with("user-001", UserPersona.AGENT)


async def test_reject_stores_reason_and_sets_rejected():
    """reject() stores rejection_reason and transitions status to REJECTED."""
    reason = "Does not meet coverage area requirements for this region"
    pending_app = _make_application(status=AgentApplicationStatus.PENDING)
    rejected_app = _make_application(status=AgentApplicationStatus.REJECTED, rejection_reason=reason)
    svc = _make_service()
    svc._repo.get_model = AsyncMock(side_effect=[pending_app, rejected_app])
    svc._repo.update = AsyncMock()

    result = await svc.reject("app-001", "admin-001", reason)

    svc._repo.update.assert_called_once()
    update_dto = svc._repo.update.call_args[0][1]
    assert update_dto.status == AgentApplicationStatus.REJECTED
    assert "coverage area" in update_dto.rejection_reason
    assert result.rejection_reason == reason


async def test_reject_short_reason_raises():
    """Rejection reason shorter than 30 characters raises ValidationException."""
    from main.app.domain.user.agent.validator import AgentApplicationValidator
    validator = AgentApplicationValidator()
    with pytest.raises(ValidationException, match="30"):
        validator.assert_rejection_reason("Too short")
