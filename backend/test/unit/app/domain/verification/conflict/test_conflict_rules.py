"""Unit tests for conflict detection rules (S29 — D15 provisional set)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from main.app.domain.verification.conflict.rules import (
    AuthenticityConflictRule,
    BoundaryDivergenceRule,
    OccupancyMismatchRule,
    OwnerNameMismatchRule,
    run_all_rules,
)
from main.app.domain.verification.task.models import Task, TaskRole, TaskStatus


VID = "ver-test"


def _task(role: TaskRole, payload: dict) -> Task:
    t = MagicMock(spec=Task)
    t.role = role.value
    t.status = TaskStatus.SUBMITTED.value
    t.draft_payload = json.dumps(payload)
    return t


# ── Rule 1: OccupancyMismatchRule ──────────────────────────────────────────────

class TestOccupancyMismatchRule:
    rule = OccupancyMismatchRule()

    def test_fires_when_field_vacant_registry_occupied(self):
        tasks = [
            _task(TaskRole.FIELD, {"occupancy_status": "VACANT"}),
            _task(TaskRole.REGISTRY, {"registered_occupancy": "OCCUPIED"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is not None
        assert result.rule_id == "OCCUPANCY_MISMATCH"

    def test_silent_when_consistent(self):
        tasks = [
            _task(TaskRole.FIELD, {"occupancy_status": "OCCUPIED"}),
            _task(TaskRole.REGISTRY, {"registered_occupancy": "OCCUPIED"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None

    def test_silent_when_field_payload_missing(self):
        tasks = [
            _task(TaskRole.FIELD, {}),
            _task(TaskRole.REGISTRY, {"registered_occupancy": "OCCUPIED"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None


# ── Rule 2: BoundaryDivergenceRule ─────────────────────────────────────────────

class TestBoundaryDivergenceRule:
    rule = BoundaryDivergenceRule()

    def test_fires_when_divergence_exceeds_5m(self):
        # ~6.6 m apart in Lagos area
        tasks = [
            _task(TaskRole.SURVEYOR, {"boundary_coords": {"lat": 6.5244, "lng": 3.3792}}),
            _task(TaskRole.REGISTRY, {"survey_plan_coords": {"lat": 6.5245, "lng": 3.3792}}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is not None
        assert result.rule_id == "BOUNDARY_DIVERGENCE"

    def test_silent_when_within_threshold(self):
        # exact same point
        tasks = [
            _task(TaskRole.SURVEYOR, {"boundary_coords": {"lat": 6.5244, "lng": 3.3792}}),
            _task(TaskRole.REGISTRY, {"survey_plan_coords": {"lat": 6.5244, "lng": 3.3792}}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None

    def test_silent_when_coords_missing(self):
        tasks = [
            _task(TaskRole.SURVEYOR, {}),
            _task(TaskRole.REGISTRY, {}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None


# ── Rule 3: AuthenticityConflictRule ───────────────────────────────────────────

class TestAuthenticityConflictRule:
    rule = AuthenticityConflictRule()

    def test_fires_when_lawyer_forged_registry_authentic(self):
        tasks = [
            _task(TaskRole.LAWYER, {"document_authenticity": "FORGED"}),
            _task(TaskRole.REGISTRY, {"title_doc_assessment": "AUTHENTIC"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is not None
        assert result.rule_id == "AUTHENTICITY_CONFLICT"

    def test_silent_when_both_authentic(self):
        tasks = [
            _task(TaskRole.LAWYER, {"document_authenticity": "AUTHENTIC"}),
            _task(TaskRole.REGISTRY, {"title_doc_assessment": "AUTHENTIC"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None

    def test_silent_when_no_lawyer_task(self):
        tasks = [_task(TaskRole.REGISTRY, {"title_doc_assessment": "AUTHENTIC"})]
        result = self.rule.check(tasks, VID)
        assert result is None


# ── Rule 4: OwnerNameMismatchRule ──────────────────────────────────────────────

class TestOwnerNameMismatchRule:
    rule = OwnerNameMismatchRule()

    def test_fires_when_names_differ(self):
        tasks = [
            _task(TaskRole.REGISTRY, {
                "ownership_chain": [{"name": "Emeka Okafor"}, {"name": "Chidi Obi"}],
                "seller_name": "John Doe",
            }),
        ]
        result = self.rule.check(tasks, VID)
        assert result is not None
        assert result.rule_id == "OWNER_NAME_MISMATCH"

    def test_silent_when_names_match(self):
        tasks = [
            _task(TaskRole.REGISTRY, {
                "ownership_chain": [{"name": "John Doe"}],
                "seller_name": "john doe",  # case-insensitive
            }),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None

    def test_silent_when_chain_empty(self):
        tasks = [
            _task(TaskRole.REGISTRY, {"ownership_chain": [], "seller_name": "John Doe"}),
        ]
        result = self.rule.check(tasks, VID)
        assert result is None


# ── run_all_rules integration ──────────────────────────────────────────────────

class TestRunAllRules:
    def test_no_flags_for_clean_data(self):
        tasks = [
            _task(TaskRole.FIELD, {"occupancy_status": "OCCUPIED"}),
            _task(TaskRole.SURVEYOR, {"boundary_coords": {"lat": 6.5244, "lng": 3.3792}}),
            _task(TaskRole.REGISTRY, {
                "registered_occupancy": "OCCUPIED",
                "survey_plan_coords": {"lat": 6.5244, "lng": 3.3792},
                "title_doc_assessment": "AUTHENTIC",
                "ownership_chain": [{"name": "John Doe"}],
                "seller_name": "john doe",
            }),
            _task(TaskRole.LAWYER, {"document_authenticity": "AUTHENTIC"}),
        ]
        flags = run_all_rules(tasks, VID)
        assert flags == []

    def test_multiple_flags_detected(self):
        tasks = [
            _task(TaskRole.FIELD, {"occupancy_status": "VACANT"}),
            _task(TaskRole.REGISTRY, {
                "registered_occupancy": "OCCUPIED",
                "title_doc_assessment": "AUTHENTIC",
                "ownership_chain": [{"name": "Wrong Name"}],
                "seller_name": "john doe",
            }),
            _task(TaskRole.LAWYER, {"document_authenticity": "FORGED"}),
        ]
        flags = run_all_rules(tasks, VID)
        rule_ids = {f.rule_id for f in flags}
        assert "OCCUPANCY_MISMATCH" in rule_ids
        assert "AUTHENTICITY_CONFLICT" in rule_ids
        assert "OWNER_NAME_MISMATCH" in rule_ids
