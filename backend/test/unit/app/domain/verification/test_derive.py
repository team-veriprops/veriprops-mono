"""Unit tests for PRD §0.3 derived global state rules.

Each test maps directly to a numbered rule from the PRD so failures are
immediately traceable. No mocking needed — derive_status is a pure function.
"""
import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.state_machine.derive import derive_status

S = VerificationStatus


# ── Terminal and externally-managed states (rules 1–2) ────────────────────

class TestPreservedStates:
    @pytest.mark.parametrize("terminal", [
        S.CANCELLED, S.REFUNDED, S.FAILED,
    ])
    def test_terminal_states_preserved(self, terminal):
        assert derive_status(terminal, ["APPROVED", "APPROVED"]) == terminal

    def test_disputed_preserved(self):
        assert derive_status(S.DISPUTED, ["APPROVED", "APPROVED"]) == S.DISPUTED

    def test_terminal_with_empty_tasks(self):
        assert derive_status(S.CANCELLED, []) == S.CANCELLED


# ── Pre-payment passthrough (rule 3) ──────────────────────────────────────

class TestPrePaymentPassthrough:
    @pytest.mark.parametrize("pre_payment", [
        S.DRAFT, S.SUBMITTED, S.PAYMENT_PENDING,
    ])
    def test_pre_payment_states_not_derived(self, pre_payment):
        assert derive_status(pre_payment, ["ASSIGNED"]) == pre_payment

    def test_pre_payment_with_all_approved(self):
        assert derive_status(S.DRAFT, ["APPROVED"]) == S.DRAFT


# ── Rule 4: PAID — no tasks assigned yet ──────────────────────────────────

class TestRulePaid:
    def test_paid_no_tasks(self):
        assert derive_status(S.PAID, []) == S.PAID

    def test_paid_all_pending(self):
        assert derive_status(S.PAID, ["PENDING", "PENDING"]) == S.PAID

    def test_in_progress_all_pending(self):
        # Even from IN_PROGRESS, if all tasks are pending → PAID
        assert derive_status(S.IN_PROGRESS, ["PENDING"]) == S.PAID


# ── Rule 5: IN_PROGRESS — ≥1 active task ─────────────────────────────────

class TestRuleInProgress:
    @pytest.mark.parametrize("active_state", [
        "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "REJECTED",
    ])
    def test_active_task_fires_in_progress_from_paid(self, active_state):
        assert derive_status(S.PAID, [active_state]) == S.IN_PROGRESS

    def test_mixed_active_and_pending(self):
        assert derive_status(S.PAID, ["PENDING", "ASSIGNED"]) == S.IN_PROGRESS

    def test_rejected_task_regresses_under_review(self):
        # §0.3 rule 6: REJECTED from UNDER_REVIEW → IN_PROGRESS
        assert derive_status(S.UNDER_REVIEW, ["SUBMITTED", "REJECTED"]) == S.IN_PROGRESS

    def test_in_progress_with_single_rejected(self):
        assert derive_status(S.IN_PROGRESS, ["REJECTED"]) == S.IN_PROGRESS


# ── Rule 6: UNDER_REVIEW — all settled, ≥1 submitted ─────────────────────

class TestRuleUnderReview:
    def test_all_submitted(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "SUBMITTED"]) == S.UNDER_REVIEW

    def test_mixed_submitted_and_approved(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "APPROVED"]) == S.UNDER_REVIEW

    def test_single_submitted(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED"]) == S.UNDER_REVIEW


# ── Rule 7: COMPLETED — all approved ─────────────────────────────────────

class TestRuleCompleted:
    def test_all_approved(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED", "APPROVED"]) == S.COMPLETED

    def test_single_approved(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED"]) == S.COMPLETED

    def test_empty_tasks_does_not_complete(self):
        # All-approved requires a non-empty list
        assert derive_status(S.UNDER_REVIEW, []) != S.COMPLETED


# ── Ordering-dependence ───────────────────────────────────────────────────

class TestOrdering:
    def test_rule5_beats_rule6(self):
        # REJECTED is active (rule 5) even though other tasks are SUBMITTED (rule 6).
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "REJECTED"]) == S.IN_PROGRESS

    def test_rule4_beats_rule6_no_tasks(self):
        # Empty task list → PAID, not UNDER_REVIEW
        assert derive_status(S.PAID, []) == S.PAID

    def test_single_active_beats_all_settled(self):
        # Mixed: one ASSIGNED prevents UNDER_REVIEW
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "ASSIGNED"]) == S.IN_PROGRESS


# ── Acceptance fixtures from execution-plan.md ───────────────────────────

class TestAcceptanceFixtures:
    def test_assigning_first_task_moves_paid_to_in_progress(self):
        assert derive_status(S.PAID, ["ASSIGNED"]) == S.IN_PROGRESS

    def test_all_tasks_submitted_moves_to_under_review(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "SUBMITTED"]) == S.UNDER_REVIEW

    def test_all_tasks_approved_moves_to_completed(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED", "APPROVED"]) == S.COMPLETED
