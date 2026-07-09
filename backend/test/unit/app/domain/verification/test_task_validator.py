"""Role submission validation (§7.3) — the four role forms."""
import pytest

from main.app.core.state.status import AgentRole
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
