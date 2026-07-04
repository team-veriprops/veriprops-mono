"""Customer label projection (§9.2/§9.3): exact status/task/SLA strings + provisional
interim copy. These are the source-of-truth strings the frontend renders verbatim."""
import pytest

from main.app.core.sla import SlaHealth
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus
from main.app.domain.verification.tracking.labels import (
    customer_sla_label,
    customer_status_label,
    customer_task_state,
    interim_message,
)


class TestStatusLabels:
    @pytest.mark.parametrize("status,expected", [
        (VerificationStatus.PAID, "Payment Confirmed — Agents Being Assigned"),
        (VerificationStatus.IN_PROGRESS, "Verification In Progress"),
        (VerificationStatus.UNDER_REVIEW, "Under Review"),
        (VerificationStatus.COMPLETED, "Completed ✅"),
        (VerificationStatus.DISPUTED, "Dispute Under Review"),
        (VerificationStatus.FAILED, "Could Not Be Completed"),
        (VerificationStatus.REFUNDED, "Refunded"),
    ])
    def test_status_label(self, status, expected):
        assert customer_status_label(status) == expected

    def test_every_status_has_a_label(self):
        for s in VerificationStatus:
            assert customer_status_label(s)


class TestTaskCollapse:
    @pytest.mark.parametrize("state,expected", [
        (TaskState.PENDING, "Pending"),
        (TaskState.ASSIGNED, "Pending"),
        (TaskState.ACCEPTED, "Pending"),
        (TaskState.IN_PROGRESS, "In Progress"),
        (TaskState.SUBMITTED, "In Progress"),
        (TaskState.REJECTED, "In Progress"),
        (TaskState.APPROVED, "Completed"),
    ])
    def test_task_collapse(self, state, expected):
        assert customer_task_state(state) == expected


class TestSlaLabel:
    def test_maps_health_to_customer_wording(self):
        assert customer_sla_label(SlaHealth.ON_TRACK) == "On track"
        assert customer_sla_label(SlaHealth.AT_RISK) == "Running late"
        assert customer_sla_label(SlaHealth.OVERDUE) == "Delayed"
        assert customer_sla_label(SlaHealth.NONE) is None


class TestInterimMessage:
    def test_is_provisional_for_every_role(self):
        for role in AgentRole:
            msg = interim_message(role)
            # provisional framing guards against a later adverse finding reading as a switch
            assert "so far" in msg.lower()
