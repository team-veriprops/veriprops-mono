"""Unit tests for the reusable StateMachine and all three PRD state tables.

Covers:
  - StateMachine behaviour (self-loop, terminal, missing-state, custom resource label)
  - Verification machine: all 8 states × valid/invalid transitions  (PRD §0.2)
  - Task machine: all 7 states × valid/invalid transitions           (PRD §5)
  - Report machine: all 3 states × valid/invalid transitions         (PRD §8)
  - IllegalStateTransitionException attributes (from_state / to_state)
  - is_terminal() and allowed_transitions() helpers
  - Re-export from verification/state_machine/__init__ is intact
"""
import pytest

from main.appodus_utils.exception.exceptions import (
    IllegalStateTransitionException,
    InvalidResourceStateException,
)
from main.app.state.machine import (
    REPORT_TERMINAL,
    REPORT_TRANSITIONS,
    TASK_TERMINAL,
    TASK_TRANSITIONS,
    VERIFICATION_TERMINAL,
    VERIFICATION_TRANSITIONS,
    StateMachine,
    report_state_machine,
    task_state_machine,
    verification_state_machine,
)


# ── StateMachine primitives ───────────────────────────────────────────────────

class TestStateMachinePrimitives:
    def test_self_loop_is_allowed(self):
        sm = StateMachine({"A": {"B"}})
        sm.assert_can_transition("A", "A")  # must not raise

    def test_valid_transition_does_not_raise(self):
        sm = StateMachine({"A": {"B"}})
        sm.assert_can_transition("A", "B")

    def test_invalid_transition_raises(self):
        sm = StateMachine({"A": {"B"}})
        with pytest.raises(IllegalStateTransitionException):
            sm.assert_can_transition("A", "C")

    def test_terminal_state_blocks_all_exits(self):
        sm = StateMachine({"A": {"B"}, "B": {"C"}}, terminal={"B"})
        with pytest.raises(IllegalStateTransitionException):
            sm.assert_can_transition("B", "C")

    def test_terminal_state_self_loop_allowed(self):
        sm = StateMachine({}, terminal={"DONE"})
        sm.assert_can_transition("DONE", "DONE")  # must not raise

    def test_unknown_source_state_raises(self):
        sm = StateMachine({"A": {"B"}})
        with pytest.raises(IllegalStateTransitionException):
            sm.assert_can_transition("GHOST", "B")

    def test_exception_carries_from_and_to(self):
        sm = StateMachine({"A": {"B"}})
        with pytest.raises(IllegalStateTransitionException) as exc_info:
            sm.assert_can_transition("A", "Z")
        err = exc_info.value
        assert err.from_state == "A"
        assert err.to_state == "Z"

    def test_exception_is_subclass_of_invalid_resource_state(self):
        sm = StateMachine({"A": {"B"}})
        with pytest.raises(InvalidResourceStateException):
            sm.assert_can_transition("A", "Z")

    def test_resource_label_in_message(self):
        sm = StateMachine({"A": {"B"}})
        with pytest.raises(IllegalStateTransitionException) as exc_info:
            sm.assert_can_transition("A", "Z", resource="Verification")
        assert "Verification" in exc_info.value.message

    def test_is_terminal_true(self):
        sm = StateMachine({}, terminal={"DONE"})
        assert sm.is_terminal("DONE") is True

    def test_is_terminal_false(self):
        sm = StateMachine({"A": {"B"}})
        assert sm.is_terminal("A") is False

    def test_allowed_transitions_normal_state(self):
        sm = StateMachine({"A": {"B", "C"}})
        assert sm.allowed_transitions("A") == {"B", "C"}

    def test_allowed_transitions_terminal_state(self):
        sm = StateMachine({"A": {"B"}}, terminal={"B"})
        assert sm.allowed_transitions("B") == set()

    def test_allowed_transitions_unknown_state(self):
        sm = StateMachine({"A": {"B"}})
        assert sm.allowed_transitions("GHOST") == set()


# ── Verification state machine (PRD §0.2) ────────────────────────────────────
#
# States: DRAFT, SUBMITTED, PAYMENT_PENDING, PAID, IN_PROGRESS,
#         UNDER_REVIEW, COMPLETED, DISPUTED
# Terminal: CANCELLED, REFUNDED, FAILED

VERIFICATION_VALID: list[tuple[str, str]] = [
    ("DRAFT", "SUBMITTED"),
    ("DRAFT", "CANCELLED"),
    ("SUBMITTED", "PAYMENT_PENDING"),
    ("SUBMITTED", "CANCELLED"),
    ("PAYMENT_PENDING", "PAID"),
    ("PAYMENT_PENDING", "CANCELLED"),
    ("PAYMENT_PENDING", "FAILED"),
    ("PAID", "IN_PROGRESS"),
    ("PAID", "CANCELLED"),
    ("PAID", "REFUNDED"),
    ("PAID", "FAILED"),
    ("IN_PROGRESS", "UNDER_REVIEW"),
    ("IN_PROGRESS", "FAILED"),
    ("IN_PROGRESS", "CANCELLED"),
    ("UNDER_REVIEW", "COMPLETED"),
    ("UNDER_REVIEW", "IN_PROGRESS"),
    ("UNDER_REVIEW", "FAILED"),
    ("COMPLETED", "DISPUTED"),
    ("DISPUTED", "COMPLETED"),
    ("DISPUTED", "REFUNDED"),
]

VERIFICATION_INVALID: list[tuple[str, str]] = [
    ("DRAFT", "PAID"),
    ("DRAFT", "IN_PROGRESS"),
    ("SUBMITTED", "PAID"),
    ("PAYMENT_PENDING", "IN_PROGRESS"),
    ("PAID", "SUBMITTED"),
    ("IN_PROGRESS", "DRAFT"),
    ("UNDER_REVIEW", "DRAFT"),
    ("UNDER_REVIEW", "SUBMITTED"),
    ("COMPLETED", "CANCELLED"),  # COMPLETED is NOT terminal but CANCELLED is not allowed from it
    ("COMPLETED", "REFUNDED"),   # REFUNDED not allowed directly from COMPLETED
    ("DISPUTED", "DRAFT"),
    ("DISPUTED", "CANCELLED"),
]

VERIFICATION_TERMINAL_EXITS: list[tuple[str, str]] = [
    ("CANCELLED", "DRAFT"),
    ("CANCELLED", "SUBMITTED"),
    ("REFUNDED", "COMPLETED"),
    ("FAILED", "IN_PROGRESS"),
]


class TestVerificationStateMachine:
    @pytest.mark.parametrize("from_s,to_s", VERIFICATION_VALID)
    def test_valid_transition(self, from_s: str, to_s: str):
        verification_state_machine.assert_can_transition(from_s, to_s, resource="Verification")

    @pytest.mark.parametrize("from_s,to_s", VERIFICATION_INVALID)
    def test_invalid_transition(self, from_s: str, to_s: str):
        with pytest.raises(IllegalStateTransitionException):
            verification_state_machine.assert_can_transition(from_s, to_s, resource="Verification")

    @pytest.mark.parametrize("terminal,target", VERIFICATION_TERMINAL_EXITS)
    def test_terminal_state_raises(self, terminal: str, target: str):
        with pytest.raises(IllegalStateTransitionException) as exc_info:
            verification_state_machine.assert_can_transition(terminal, target, resource="Verification")
        assert exc_info.value.from_state == terminal

    def test_terminal_states_are_correct(self):
        for t in ("CANCELLED", "REFUNDED", "FAILED"):
            assert verification_state_machine.is_terminal(t) is True

    def test_non_terminal_states_not_terminal(self):
        for s in ("DRAFT", "SUBMITTED", "PAYMENT_PENDING", "PAID", "IN_PROGRESS", "UNDER_REVIEW", "COMPLETED", "DISPUTED"):
            assert verification_state_machine.is_terminal(s) is False

    def test_transition_table_covers_all_non_terminal_states(self):
        non_terminal = {
            "DRAFT", "SUBMITTED", "PAYMENT_PENDING", "PAID",
            "IN_PROGRESS", "UNDER_REVIEW", "COMPLETED", "DISPUTED",
        }
        assert set(VERIFICATION_TRANSITIONS.keys()) == non_terminal

    def test_terminal_set_matches_constants(self):
        assert VERIFICATION_TERMINAL == {"CANCELLED", "REFUNDED", "FAILED"}

    def test_re_export_from_verification_domain_module(self):
        from main.app.domain.verification.state_machine import verification_state_machine as vsm  # noqa: F401
        vsm.assert_can_transition("DRAFT", "SUBMITTED")  # must not raise


# ── Task state machine (PRD §5) ──────────────────────────────────────────────
#
# States: PENDING, ASSIGNED, ACCEPTED, IN_PROGRESS, SUBMITTED, REJECTED, APPROVED
# Terminal: APPROVED

TASK_VALID: list[tuple[str, str]] = [
    # main path
    ("PENDING", "ASSIGNED"),
    ("ASSIGNED", "ACCEPTED"),
    ("ACCEPTED", "IN_PROGRESS"),
    ("IN_PROGRESS", "SUBMITTED"),
    ("SUBMITTED", "APPROVED"),
    # detours
    ("ASSIGNED", "PENDING"),      # decline / no-show timeout → back to pool
    ("SUBMITTED", "REJECTED"),    # admin rejects
    ("REJECTED", "IN_PROGRESS"),  # agent reworks
]

TASK_INVALID: list[tuple[str, str]] = [
    ("PENDING", "ACCEPTED"),       # must go via ASSIGNED first
    ("PENDING", "IN_PROGRESS"),
    ("PENDING", "SUBMITTED"),
    ("ASSIGNED", "IN_PROGRESS"),   # must ACCEPT first
    ("ASSIGNED", "SUBMITTED"),
    ("ACCEPTED", "PENDING"),       # cannot un-accept once accepted
    ("ACCEPTED", "SUBMITTED"),     # must pass through IN_PROGRESS
    ("IN_PROGRESS", "PENDING"),
    ("IN_PROGRESS", "ASSIGNED"),
    ("IN_PROGRESS", "APPROVED"),   # must submit first
    ("SUBMITTED", "IN_PROGRESS"),  # must go via REJECTED for rework
    ("SUBMITTED", "PENDING"),
    ("REJECTED", "PENDING"),
    ("REJECTED", "SUBMITTED"),     # must rework (go to IN_PROGRESS) first
    ("REJECTED", "APPROVED"),
]

TASK_TERMINAL_EXITS: list[tuple[str, str]] = [
    ("APPROVED", "PENDING"),
    ("APPROVED", "IN_PROGRESS"),
    ("APPROVED", "SUBMITTED"),
]


class TestTaskStateMachine:
    @pytest.mark.parametrize("from_s,to_s", TASK_VALID)
    def test_valid_transition(self, from_s: str, to_s: str):
        task_state_machine.assert_can_transition(from_s, to_s, resource="Task")

    @pytest.mark.parametrize("from_s,to_s", TASK_INVALID)
    def test_invalid_transition(self, from_s: str, to_s: str):
        with pytest.raises(IllegalStateTransitionException):
            task_state_machine.assert_can_transition(from_s, to_s, resource="Task")

    @pytest.mark.parametrize("terminal,target", TASK_TERMINAL_EXITS)
    def test_terminal_state_raises(self, terminal: str, target: str):
        with pytest.raises(IllegalStateTransitionException):
            task_state_machine.assert_can_transition(terminal, target, resource="Task")

    def test_approved_is_terminal(self):
        assert task_state_machine.is_terminal("APPROVED") is True

    def test_non_terminal_states(self):
        for s in ("PENDING", "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "SUBMITTED", "REJECTED"):
            assert task_state_machine.is_terminal(s) is False

    def test_terminal_set_matches_constants(self):
        assert TASK_TERMINAL == {"APPROVED"}

    def test_transition_table_covers_all_non_terminal_states(self):
        non_terminal = {"PENDING", "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "SUBMITTED", "REJECTED"}
        assert set(TASK_TRANSITIONS.keys()) == non_terminal

    def test_decline_returns_to_pool(self):
        """ASSIGNED → PENDING models an agent declining or timing out (PRD §5)."""
        task_state_machine.assert_can_transition("ASSIGNED", "PENDING", resource="Task")

    def test_rework_path(self):
        """Admin reject → REJECTED → agent reworks → IN_PROGRESS (PRD §5 detour)."""
        task_state_machine.assert_can_transition("SUBMITTED", "REJECTED", resource="Task")
        task_state_machine.assert_can_transition("REJECTED", "IN_PROGRESS", resource="Task")


# ── Report state machine (PRD §8) ────────────────────────────────────────────
#
# States: DRAFT, RELEASED, SUPERSEDED
# Terminal: SUPERSEDED

REPORT_VALID: list[tuple[str, str]] = [
    ("DRAFT", "RELEASED"),       # admin releases report
    ("RELEASED", "SUPERSEDED"),  # new version supersedes this one
]

REPORT_INVALID: list[tuple[str, str]] = [
    ("DRAFT", "SUPERSEDED"),   # cannot skip RELEASED
    ("RELEASED", "DRAFT"),     # no rollback to draft
]

REPORT_TERMINAL_EXITS: list[tuple[str, str]] = [
    ("SUPERSEDED", "DRAFT"),
    ("SUPERSEDED", "RELEASED"),
]


class TestReportStateMachine:
    @pytest.mark.parametrize("from_s,to_s", REPORT_VALID)
    def test_valid_transition(self, from_s: str, to_s: str):
        report_state_machine.assert_can_transition(from_s, to_s, resource="Report")

    @pytest.mark.parametrize("from_s,to_s", REPORT_INVALID)
    def test_invalid_transition(self, from_s: str, to_s: str):
        with pytest.raises(IllegalStateTransitionException):
            report_state_machine.assert_can_transition(from_s, to_s, resource="Report")

    @pytest.mark.parametrize("terminal,target", REPORT_TERMINAL_EXITS)
    def test_terminal_state_raises(self, terminal: str, target: str):
        with pytest.raises(IllegalStateTransitionException):
            report_state_machine.assert_can_transition(terminal, target, resource="Report")

    def test_superseded_is_terminal(self):
        assert report_state_machine.is_terminal("SUPERSEDED") is True

    def test_non_terminal_states(self):
        for s in ("DRAFT", "RELEASED"):
            assert report_state_machine.is_terminal(s) is False

    def test_terminal_set_matches_constants(self):
        assert REPORT_TERMINAL == {"SUPERSEDED"}

    def test_transition_table_covers_all_non_terminal_states(self):
        non_terminal = {"DRAFT", "RELEASED"}
        assert set(REPORT_TRANSITIONS.keys()) == non_terminal

    def test_version_supersede_semantics(self):
        """PRD §8: releasing a new version moves old report RELEASED → SUPERSEDED."""
        report_state_machine.assert_can_transition("RELEASED", "SUPERSEDED", resource="Report")
        # the superseded report is now frozen
        assert report_state_machine.is_terminal("SUPERSEDED") is True
        with pytest.raises(IllegalStateTransitionException):
            report_state_machine.assert_can_transition("SUPERSEDED", "RELEASED", resource="Report")

    def test_allowed_transitions_draft(self):
        assert report_state_machine.allowed_transitions("DRAFT") == {"RELEASED"}

    def test_allowed_transitions_released(self):
        assert report_state_machine.allowed_transitions("RELEASED") == {"SUPERSEDED"}

    def test_allowed_transitions_superseded(self):
        assert report_state_machine.allowed_transitions("SUPERSEDED") == set()
