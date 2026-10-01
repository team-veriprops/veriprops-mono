"""The admin task grid's wire contract (§8.3).

An approval is deliberately *not* a state change — ``approve_task`` leaves the task
SUBMITTED and records the verdict in ``review_decision`` — so that field is the only thing
that tells an admin their approval registered. Both admin surfaces build ``TaskDto`` with a
hand-written mapper, and a field omitted there is invisible to the browser however faithfully
the service wrote it to the row.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from main.app.core.state.status import AgentRole, TaskState, VerificationTier
from main.app.domain.verification.admin.service import AdminVerificationService
from main.app.domain.verification.review.controller import _task_dto as review_task_dto
from main.app.domain.verification.task.models import ReviewDecision


def _row(review=ReviewDecision.APPROVED.value, quality=95, rejection_reason=None):
    """A task row as the repo hands it over: reviewed, but still SUBMITTED."""
    return SimpleNamespace(
        id="task-registry", verification_id="v-1", role=AgentRole.REGISTRY.value,
        tier=VerificationTier.STANDARD.value, state=TaskState.SUBMITTED.value,
        assigned_agent_id="agent-1", assignment_mode=None, in_pool=False,
        pool_expires_at=None, accept_deadline_at=None, decline_count=0,
        remote_bonus_minor=None, assigned_at=None, accepted_at=None,
        submitted_at=None, approved_at=None,
        review_decision=review, review_quality=quality, rejection_reason=rejection_reason,
    )


def _admin_task_dto(row):
    """The admin verification-detail mapper, which is an instance method with no deps."""
    return AdminVerificationService._task_dto(object.__new__(AdminVerificationService), row)


class TestReviewedTaskReachesTheBrowser:
    def test_the_review_page_carries_the_decision(self):
        dto = review_task_dto(_row())
        assert dto.review_decision == ReviewDecision.APPROVED
        assert dto.review_quality == 95

    def test_the_verification_detail_carries_the_decision(self):
        dto = _admin_task_dto(_row())
        assert dto.review_decision == ReviewDecision.APPROVED

    def test_a_returned_task_carries_the_reason_it_came_back(self):
        row = _row(review=ReviewDecision.REJECTED.value, rejection_reason="Photo too dark.")
        assert review_task_dto(row).rejection_reason == "Photo too dark."

    def test_both_admin_mappers_carry_the_remote_bonus(self):
        # The bonus is paid as its own commission line (D97); an admin reviewing the task must
        # see it on either surface, not only on the verification detail.
        row = _row()
        row.remote_bonus_minor = 500_000
        assert review_task_dto(row).remote_bonus_minor == 500_000
        assert _admin_task_dto(row).remote_bonus_minor == 500_000

    def test_an_unreviewed_task_carries_no_decision(self):
        assert review_task_dto(_row(review=None, quality=None)).review_decision is None

    def test_the_decision_travels_as_camel_case(self):
        # The frontend reads `reviewDecision`; the alias generator owns that translation.
        wire = review_task_dto(_row()).model_dump(by_alias=True)
        assert wire["reviewDecision"] == ReviewDecision.APPROVED.value
        assert "review_decision" not in wire


class TestCommissionLineKind:
    def test_the_verification_detail_labels_a_remote_bonus_line(self):
        # §20.1 / D97: the admin sees a bonus as its own line beside the fixed commission.
        from main.app.domain.commission.models import CommissionKind, CommissionStatus
        row = SimpleNamespace(
            id="c-1", verification_id="v-1", task_id="t-1", agent_id="agent-1",
            role=AgentRole.FIELD.value, tier=VerificationTier.STANDARD.value,
            kind=CommissionKind.REMOTE_BONUS.value, amount_minor=500_000, currency="NGN",
            status=CommissionStatus.CLEARING.value, clearing_until=None,
            date_created=datetime(2026, 9, 27, tzinfo=timezone.utc),
        )
        svc = object.__new__(AdminVerificationService)
        assert svc._commission_dto(row).kind == CommissionKind.REMOTE_BONUS
