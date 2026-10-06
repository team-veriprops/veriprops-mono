"""Role submission validation (§12.2) — the four role forms."""
import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.verification.task.models import LegalRiskLevel
from main.app.domain.verification.task.validator import validate_submission
from main.appodus_utils.exception.exceptions import ValidationException


class TestValidateSubmission:
    @pytest.mark.parametrize("role,payload", [
        (AgentRole.REGISTRY, {"registered_owner": "A", "title_search_result": "clean", "search_reference": "R1"}),
        (AgentRole.FIELD, {"occupancy_status": "vacant", "physical_condition": "good"}),
        (AgentRole.SURVEYOR, {"area_sqm": 500, "beacon_status": "intact"}),
        (AgentRole.LAWYER, {"legal_opinion": "sound", "risk_level": "low", "recommendation": "proceed"}),
    ])
    def test_complete_forms_pass(self, role, payload):
        validate_submission(role, payload)  # no raise

    @pytest.mark.parametrize("role,payload", [
        (AgentRole.REGISTRY, {"registered_owner": "A"}),
        (AgentRole.FIELD, {"occupancy_status": ""}),
        (AgentRole.SURVEYOR, {"area_sqm": 500}),
        (AgentRole.LAWYER, {"legal_opinion": "sound", "risk_level": "low"}),
    ])
    def test_incomplete_forms_raise(self, role, payload):
        with pytest.raises(ValidationException):
            validate_submission(role, payload)

    def test_non_object_payload_raises(self):
        with pytest.raises(ValidationException):
            validate_submission(AgentRole.FIELD, "not-a-dict")  # type: ignore[arg-type]


_LAWYER = {"legal_opinion": "sound", "recommendation": "proceed"}


class TestLegalRiskLevel:
    """The lawyer's risk level is one of a fixed set, so the HIGH-risk review conflict (§8.2)
    reads a value it can rely on rather than whatever was typed."""

    @pytest.mark.parametrize("typed", ["high", " High ", "HIGH"])
    def test_any_casing_is_stored_as_the_enum_value(self, typed):
        normalised = validate_submission(AgentRole.LAWYER, {**_LAWYER, "risk_level": typed})

        assert normalised["risk_level"] == LegalRiskLevel.HIGH.value

    def test_a_value_outside_the_set_is_refused_with_the_choices(self):
        with pytest.raises(ValidationException) as exc:
            validate_submission(AgentRole.LAWYER, {**_LAWYER, "risk_level": "very high"})

        assert "Low, Medium, High" in exc.value.message

    def test_the_callers_payload_is_left_as_sent(self):
        payload = {**_LAWYER, "risk_level": "low"}

        validate_submission(AgentRole.LAWYER, payload)

        assert payload["risk_level"] == "low"

    def test_other_roles_pass_through_unchanged(self):
        payload = {"occupancy_status": "vacant", "physical_condition": "good"}

        assert validate_submission(AgentRole.FIELD, payload) == payload
