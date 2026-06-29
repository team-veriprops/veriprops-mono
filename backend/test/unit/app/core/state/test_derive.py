"""Unit tests for the verification-status derivation owner (PRD §2.5 / §4.1).

`derive_status` is a pure function, so no mocking is needed. Each test maps to a
numbered §2.5 rule (and to the acceptance fixtures in docs/execution-plan.md) so
failures are immediately traceable.
"""
import pytest

from main.app.core.state.status import VerificationStatus
from main.app.core.state.derive import derive_status

S = VerificationStatus


# ── Preserved states: terminal + dispute outcomes (admin-owned) ──────────────

class TestPreservedStates:
    @pytest.mark.parametrize("terminal", [S.CANCELLED, S.REFUNDED, S.FAILED])
    def test_terminal_states_preserved(self, terminal):
        assert derive_status(terminal, ["APPROVED", "APPROVED"]) == terminal

    def test_disputed_preserved(self):
        assert derive_status(S.DISPUTED, ["APPROVED", "APPROVED"]) == S.DISPUTED

    def test_terminal_with_empty_tasks(self):
        assert derive_status(S.CANCELLED, []) == S.CANCELLED


# ── Pre-payment passthrough ──────────────────────────────────────────────────

class TestPrePaymentPassthrough:
    @pytest.mark.parametrize("pre_payment", [S.DRAFT, S.SUBMITTED, S.PAYMENT_PENDING])
    def test_pre_payment_states_not_derived(self, pre_payment):
        assert derive_status(pre_payment, ["ASSIGNED"]) == pre_payment

    def test_pre_payment_with_all_approved(self):
        assert derive_status(S.DRAFT, ["APPROVED"]) == S.DRAFT


# ── PAID: no active work yet ─────────────────────────────────────────────────

class TestRulePaid:
    def test_paid_no_tasks(self):
        assert derive_status(S.PAID, []) == S.PAID

    def test_paid_all_pending(self):
        assert derive_status(S.PAID, ["PENDING", "PENDING"]) == S.PAID

    def test_in_progress_all_pending_regresses_to_paid(self):
        assert derive_status(S.IN_PROGRESS, ["PENDING"]) == S.PAID


# ── IN_PROGRESS: ≥1 active task ──────────────────────────────────────────────

class TestRuleInProgress:
    @pytest.mark.parametrize("active_state", ["ASSIGNED", "ACCEPTED", "IN_PROGRESS", "REJECTED"])
    def test_active_task_fires_in_progress_from_paid(self, active_state):
        assert derive_status(S.PAID, [active_state]) == S.IN_PROGRESS

    def test_mixed_active_and_pending(self):
        assert derive_status(S.PAID, ["PENDING", "ASSIGNED"]) == S.IN_PROGRESS

    def test_rejected_task_regresses_from_under_review(self):
        assert derive_status(S.UNDER_REVIEW, ["SUBMITTED", "REJECTED"]) == S.IN_PROGRESS

    def test_in_progress_with_single_rejected(self):
        assert derive_status(S.IN_PROGRESS, ["REJECTED"]) == S.IN_PROGRESS


# ── UNDER_REVIEW: all settled, ≥1 submitted ──────────────────────────────────

class TestRuleUnderReview:
    def test_all_submitted(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "SUBMITTED"]) == S.UNDER_REVIEW

    def test_mixed_submitted_and_approved(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "APPROVED"]) == S.UNDER_REVIEW

    def test_single_submitted(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED"]) == S.UNDER_REVIEW


# ── COMPLETED: all approved ──────────────────────────────────────────────────

class TestRuleCompleted:
    def test_all_approved(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED", "APPROVED"]) == S.COMPLETED

    def test_single_approved(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED"]) == S.COMPLETED

    def test_empty_tasks_does_not_complete(self):
        assert derive_status(S.UNDER_REVIEW, []) != S.COMPLETED
        assert derive_status(S.UNDER_REVIEW, []) == S.PAID


# ── Precedence / ordering ────────────────────────────────────────────────────

class TestOrdering:
    def test_active_beats_settled(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "REJECTED"]) == S.IN_PROGRESS

    def test_no_tasks_beats_review(self):
        assert derive_status(S.PAID, []) == S.PAID

    def test_single_active_beats_all_settled(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "ASSIGNED"]) == S.IN_PROGRESS


# ── Input normalization (accepts enums or raw strings) ───────────────────────

class TestInputNormalization:
    def test_accepts_string_current_status(self):
        assert derive_status("UNDER_REVIEW", ["APPROVED"]) == S.COMPLETED

    def test_accepts_enum_task_states(self):
        from main.app.core.state.status import TaskState
        assert derive_status(S.IN_PROGRESS, [TaskState.SUBMITTED, TaskState.SUBMITTED]) == S.UNDER_REVIEW


# ── Acceptance fixtures (docs/execution-plan.md) ─────────────────────────────

class TestAcceptanceFixtures:
    def test_assigning_first_task_moves_paid_to_in_progress(self):
        assert derive_status(S.PAID, ["ASSIGNED"]) == S.IN_PROGRESS

    def test_all_tasks_submitted_moves_to_under_review(self):
        assert derive_status(S.IN_PROGRESS, ["SUBMITTED", "SUBMITTED"]) == S.UNDER_REVIEW

    def test_all_tasks_approved_moves_to_completed(self):
        assert derive_status(S.UNDER_REVIEW, ["APPROVED", "APPROVED"]) == S.COMPLETED
