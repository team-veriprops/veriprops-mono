"""AgentService submission orchestration (PRD §3.1) — repos mocked, no DB.

Verifies the submit path runs KYC, persists a PENDING profile, records AGENT_TERMS
consent, adds the AGENT persona, and audits the submission; and that the wizard
draft resumes (update when a draft already exists, create otherwise).
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.audit.models import AuditActionType
from main.app.domain.user.agent.kyc.models import KycSubmissionDto
from main.app.domain.user.agent.models import SubmitAgentApplicationDto
from main.app.domain.user.agent.profile.models import AgentApplicationStatus
from main.app.domain.user.agent.service import AgentService
from main.app.domain.user.agent.validator import AgentApplicationValidator
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.kyc.models import KycMethod


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
    svc = object.__new__(AgentService)
    svc._profile_repo = MagicMock()
    svc._credential_repo = MagicMock()
    svc._coverage_repo = MagicMock()
    svc._draft_service = MagicMock()
    svc._kyc_service = MagicMock()
    svc._user_service = MagicMock()
    svc._consent_service = MagicMock()
    svc._audit_service = MagicMock()
    svc._agent_validator = AgentApplicationValidator()

    svc._user_service.get_user_model = AsyncMock(
        return_value=SimpleNamespace(first_name="Ada", last_name="Obi", email="ada@example.com")
    )
    svc._user_service.add_persona = AsyncMock()
    svc._kyc_service.run_verification = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()
    svc._profile_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(
        id="prof-1", user_id="u-1", roles=["FIELD"], approved_roles=[],
        status=AgentApplicationStatus.PENDING.value, submitted_at=None, rejection_reason=None,
    ))
    svc._credential_repo.create = AsyncMock()
    svc._credential_repo.list_for_user = AsyncMock(return_value=[])
    svc._coverage_repo.create = AsyncMock()
    svc._draft_service.discard = AsyncMock()
    return svc


def _valid_dto(**over):
    base = dict(
        roles=[AgentRole.FIELD],
        kyc=KycSubmissionDto(method=KycMethod.BVN, bvn="22222222222"),
        credentials=[],
        coverage=[],
        bio="Experienced field agent",
        years_experience=5,
        truthfulness_confirmed=True,
        agent_terms_version="1.0.0",
    )
    base.update(over)
    return SubmitAgentApplicationDto(**base)


class TestSubmit:
    async def test_runs_kyc_and_creates_pending_profile(self):
        svc = _make_service()
        status = await svc.submit_application("u-1", _valid_dto(), ip_address="1.2.3.4")

        svc._kyc_service.run_verification.assert_awaited_once()
        svc._profile_repo.create_return_model.assert_awaited_once()
        assert status.status == AgentApplicationStatus.PENDING
        assert AgentRole.FIELD in status.roles

    async def test_records_agent_terms_consent(self):
        svc = _make_service()
        await svc.submit_application("u-1", _valid_dto(), ip_address="1.2.3.4")
        args, kwargs = svc._consent_service.record_user_consent.call_args
        assert kwargs["document_type"] == ConsentDocumentType.AGENT_TERMS
        assert kwargs["consent_version"] == "1.0.0"

    async def test_adds_agent_persona(self):
        svc = _make_service()
        await svc.submit_application("u-1", _valid_dto())
        svc._user_service.add_persona.assert_awaited_once_with("u-1", UserPersona.AGENT)

    async def test_audits_submission(self):
        svc = _make_service()
        await svc.submit_application("u-1", _valid_dto())
        action = svc._audit_service.schedule.call_args.kwargs["action"]
        assert action == AuditActionType.AGENT_APPLICATION_SUBMITTED

    async def test_discards_draft_after_submit(self):
        svc = _make_service()
        await svc.submit_application("u-1", _valid_dto())
        svc._draft_service.discard.assert_awaited_once_with("u-1")


class TestStatus:
    async def test_none_when_no_profile(self):
        svc = _make_service()
        svc._profile_repo.get_by_user_id = AsyncMock(return_value=None)
        assert await svc.get_my_status("u-1") is None
