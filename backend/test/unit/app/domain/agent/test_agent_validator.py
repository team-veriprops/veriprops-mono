"""Agent application validation rules (PRD §3.1) — pure, no DB."""
import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.credential.models import (
    AgentCredentialInputDto,
    CredentialType,
)
from main.app.domain.user.agent.kyc.models import KycSubmissionDto
from main.app.domain.user.agent.models import SubmitAgentApplicationDto
from main.app.domain.user.agent.validator import AgentApplicationValidator
from main.appodus_utils.integrations.kyc.models import KycMethod
from main.appodus_utils.exception.exceptions import ValidationException

validator = AgentApplicationValidator()


def _dto(**overrides) -> SubmitAgentApplicationDto:
    base = dict(
        roles=[AgentRole.FIELD],
        kyc=KycSubmissionDto(method=KycMethod.BVN, bvn="22222222222"),
        credentials=[],
        coverage=[],
        truthfulness_confirmed=True,
        agent_terms_version="1.0.0",
    )
    base.update(overrides)
    return SubmitAgentApplicationDto(**base)


class TestRoleRules:
    def test_at_least_one_role_required(self):
        with pytest.raises(ValidationException):
            validator.validate_submission(_dto(roles=[]))

    def test_field_agent_needs_no_credential(self):
        validator.validate_submission(_dto(roles=[AgentRole.FIELD]))  # no raise


class TestConditionalCredentials:
    def test_lawyer_requires_nba_licence(self):
        with pytest.raises(ValidationException):
            validator.validate_submission(_dto(roles=[AgentRole.LAWYER], credentials=[]))

    def test_lawyer_with_nba_licence_passes(self):
        validator.validate_submission(_dto(
            roles=[AgentRole.LAWYER],
            credentials=[AgentCredentialInputDto(
                role=AgentRole.LAWYER, credential_type=CredentialType.NBA_LICENCE, licence_number="NBA-1",
            )],
        ))

    def test_surveyor_credential_type_must_match_role(self):
        with pytest.raises(ValidationException):
            validator.validate_submission(_dto(
                roles=[AgentRole.SURVEYOR],
                credentials=[AgentCredentialInputDto(
                    role=AgentRole.SURVEYOR, credential_type=CredentialType.NBA_LICENCE,
                )],
            ))


class TestConsentAndTruthfulness:
    def test_truthfulness_required(self):
        with pytest.raises(ValidationException):
            validator.validate_submission(_dto(truthfulness_confirmed=False))

    def test_agent_terms_version_required(self):
        with pytest.raises(ValidationException):
            validator.validate_submission(_dto(agent_terms_version=""))
