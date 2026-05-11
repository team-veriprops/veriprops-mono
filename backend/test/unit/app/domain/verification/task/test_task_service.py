"""Unit tests for TaskService — pool assignment, OL accept, lawyer gate, state derivation.

Covers:
- create_tasks_for_tier creates correct roles per tier
- OL accept: pool claim wins on rowcount>0; loses on rowcount=0 → 409
- agent_accept: admin-assign path checks agent_id match
- agent_decline: returns ACCEPTED task to PENDING
- save_draft: advances ACCEPTED→IN_PROGRESS on first save
- submit: lawyer gate blocks until siblings are SUBMITTED/APPROVED
- submit: trust elevation fires on first submission
- _derive_and_update_verification_status: correct status derivation
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.task.models import (
    Task,
    TaskRole,
    TaskStatus,
    TIER_ROLES,
)
from main.app.domain.verification.task.service import TaskService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)


# ── fixtures / helpers ────────────────────────────────────────────────────────

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


def _task(
    task_id: str = "task-1",
    verification_id: str = "ver-1",
    role: str = TaskRole.FIELD.value,
    status: str = TaskStatus.PENDING.value,
    agent_id: str | None = None,
    pool_released_at: datetime | None = None,
) -> Task:
    t = MagicMock(spec=Task)
    t.id = task_id
    t.verification_id = verification_id
    t.role = role
    t.status = status
    t.agent_id = agent_id
    t.pool_released_at = pool_released_at
    t.accepted_at = None
    t.submitted_at = None
    t.trust_score = None
    t.draft_payload = None
    t.date_created = datetime.now(timezone.utc)
    t.date_updated = datetime.now(timezone.utc)
    return t


def _make_service(
    tasks: List[Task] | None = None,
    claim_result: bool = True,
    verification_status: str = VerificationStatus.PAID.value,
    evidence_gps_count: int = 5,
):
    task_repo = MagicMock()
    task_repo.create_return_model = AsyncMock(
        side_effect=lambda dto: _task(
            role=dto.role.value if hasattr(dto.role, "value") else dto.role,
            status=dto.status.value if hasattr(dto.status, "value") else dto.status,
        )
    )
    task_repo.list_for_verification = AsyncMock(return_value=tasks or [])
    task_repo.list_pending_for_agent = AsyncMock(return_value=tasks or [])
    task_repo.list_active_for_agent = AsyncMock(return_value=tasks or [])
    task_repo.list_completed_for_agent = AsyncMock(return_value=tasks or [])
    task_repo.claim_task = AsyncMock(return_value=claim_result)
    task_repo.get_task = AsyncMock(return_value=tasks[0] if tasks else _task())
    task_repo.update = AsyncMock()
    task_repo.count_active_for_agent = AsyncMock(return_value=0)

    assignment_repo = MagicMock()
    assignment_repo.create_return_model = AsyncMock()

    evidence_repo = MagicMock()
    evidence_repo.count_gps_for_task = AsyncMock(return_value=evidence_gps_count)

    ver = MagicMock()
    ver.status = verification_status
    ver_repo = MagicMock()
    ver_repo.get_model = AsyncMock(return_value=ver)
    ver_repo.update = AsyncMock()

    agent_app_repo = MagicMock()
    agent_app_repo.get_by_criterion = AsyncMock(return_value=[])

    user = MagicMock()
    user.id = "agent-1"
    user.trust_status = "PENDING"
    user.first_name = "Test"
    user.last_name = "Agent"
    user_repo = MagicMock()
    user_repo.get_model = AsyncMock(return_value=user)
    user_repo.update = AsyncMock()

    audit = MagicMock()
    audit.schedule = MagicMock()

    return TaskService(
        task_repo=task_repo,
        assignment_repo=assignment_repo,
        evidence_repo=evidence_repo,
        verification_repo=ver_repo,
        agent_app_repo=agent_app_repo,
        user_repo=user_repo,
        audit=audit,
    )


# ── TIER_ROLES ────────────────────────────────────────────────────────────────

class TestTierRoles:
    def test_standard_tier_has_field_surveyor_registry(self):
        roles = TIER_ROLES["STANDARD"]
        assert set(roles) == {"FIELD", "SURVEYOR", "REGISTRY"}

    def test_premium_tier_includes_lawyer(self):
        roles = TIER_ROLES["PREMIUM"]
        assert "LAWYER" in roles

    def test_basic_tier_has_registry_only(self):
        roles = TIER_ROLES.get("BASIC", [])
        assert TaskRole.REGISTRY in roles
        assert len(roles) == 1


# ── create_tasks_for_tier ─────────────────────────────────────────────────────

class TestCreateTasksForTier:
    async def test_creates_one_task_per_role_for_standard(self):
        svc = _make_service()
        results = await svc.create_tasks_for_tier("ver-1", "STANDARD", release_immediately=True)
        assert len(results) == len(TIER_ROLES["STANDARD"])

    async def test_held_tasks_have_no_pool_released_at(self):
        svc = _make_service()
        held_task = _task(pool_released_at=None, status=TaskStatus.PENDING.value)
        svc._tasks.create_return_model = AsyncMock(return_value=held_task)
        results = await svc.create_tasks_for_tier("ver-1", "STANDARD", release_immediately=False)
        for r in results:
            assert r.pool_released_at is None

    async def test_unknown_tier_creates_no_tasks(self):
        svc = _make_service()
        results = await svc.create_tasks_for_tier("ver-1", "UNKNOWN_TIER")
        assert results == []


# ── agent_accept (pool path) ──────────────────────────────────────────────────

class TestAgentAcceptPoolPath:
    async def test_first_agent_wins(self):
        pending_task = _task(status=TaskStatus.PENDING.value)
        accepted_task = _task(status=TaskStatus.ACCEPTED.value, agent_id="agent-1")
        repo_mock = MagicMock()
        repo_mock.get_task = AsyncMock(side_effect=[pending_task, accepted_task])
        repo_mock.list_for_verification = AsyncMock(return_value=[accepted_task])
        repo_mock.claim_task = AsyncMock(return_value=True)
        repo_mock.update = AsyncMock()
        repo_mock.count_active_for_agent = AsyncMock(return_value=0)

        svc = _make_service(tasks=[pending_task])
        svc._tasks = repo_mock
        result = await svc.agent_accept("task-1", "agent-1")
        repo_mock.claim_task.assert_awaited_once_with("task-1", "agent-1")

    async def test_second_agent_gets_409(self):
        pending_task = _task(status=TaskStatus.PENDING.value)
        svc = _make_service(tasks=[pending_task], claim_result=False)
        svc._tasks.get_task = AsyncMock(return_value=pending_task)

        with pytest.raises(ResourceConflictException, match="Another agent accepted this job"):
            await svc.agent_accept("task-1", "agent-2")

    async def test_assigned_path_requires_matching_agent(self):
        assigned_task = _task(status=TaskStatus.ASSIGNED.value, agent_id="agent-correct")
        accepted_task = _task(status=TaskStatus.ACCEPTED.value, agent_id="agent-correct")
        svc = _make_service(tasks=[assigned_task])
        svc._tasks.get_task = AsyncMock(side_effect=[assigned_task, accepted_task])
        svc._tasks.list_for_verification = AsyncMock(return_value=[accepted_task])

        with pytest.raises(ValidationException, match="not assigned to you"):
            await svc.agent_accept("task-1", "agent-wrong")

    async def test_wrong_status_raises_validation_error(self):
        submitted_task = _task(status=TaskStatus.SUBMITTED.value)
        svc = _make_service(tasks=[submitted_task])
        svc._tasks.get_task = AsyncMock(return_value=submitted_task)

        with pytest.raises(ValidationException, match="cannot be accepted from status"):
            await svc.agent_accept("task-1", "agent-1")


# ── agent_decline ─────────────────────────────────────────────────────────────

class TestAgentDecline:
    async def test_accepted_task_returns_to_pending(self):
        accepted_task = _task(status=TaskStatus.ACCEPTED.value, agent_id="agent-1")
        pending_task = _task(status=TaskStatus.PENDING.value)
        svc = _make_service(tasks=[accepted_task])
        svc._tasks.get_task = AsyncMock(side_effect=[accepted_task, pending_task])
        svc._tasks.list_for_verification = AsyncMock(return_value=[pending_task])

        await svc.agent_decline("task-1", "agent-1")
        svc._tasks.update.assert_awaited_once()
        call_kwargs = svc._tasks.update.call_args[0][1]
        assert call_kwargs.status == TaskStatus.PENDING

    async def test_non_accepted_task_raises(self):
        pending_task = _task(status=TaskStatus.PENDING.value)
        svc = _make_service(tasks=[pending_task])
        svc._tasks.get_task = AsyncMock(return_value=pending_task)

        with pytest.raises(ValidationException, match="Only ACCEPTED"):
            await svc.agent_decline("task-1", "agent-1")

    async def test_wrong_agent_raises(self):
        accepted_task = _task(status=TaskStatus.ACCEPTED.value, agent_id="agent-1")
        svc = _make_service(tasks=[accepted_task])
        svc._tasks.get_task = AsyncMock(return_value=accepted_task)

        with pytest.raises(ValidationException, match="not assigned to you"):
            await svc.agent_decline("task-1", "agent-2")


# ── save_draft ────────────────────────────────────────────────────────────────

class TestSaveDraft:
    async def test_first_draft_advances_to_in_progress(self):
        accepted_task = _task(status=TaskStatus.ACCEPTED.value, agent_id="agent-1")
        in_progress_task = _task(status=TaskStatus.IN_PROGRESS.value, agent_id="agent-1")
        svc = _make_service(tasks=[accepted_task])
        svc._tasks.get_task = AsyncMock(side_effect=[accepted_task, in_progress_task])

        await svc.save_draft("task-1", "agent-1", {"conditions": "good"})
        svc._tasks.update.assert_awaited_once()
        call_kwargs = svc._tasks.update.call_args[0][1]
        assert call_kwargs.status == TaskStatus.IN_PROGRESS


# ── lawyer dependency gate ────────────────────────────────────────────────────

class TestLawyerGate:
    async def test_blocks_when_sibling_not_submitted(self):
        lawyer_task = _task(
            task_id="lawyer-1",
            role=TaskRole.LAWYER.value,
            status=TaskStatus.IN_PROGRESS.value,
            agent_id="agent-1",
        )
        field_task = _task(
            task_id="field-1",
            role=TaskRole.FIELD.value,
            status=TaskStatus.ACCEPTED.value,  # not yet submitted
        )
        submitted_task = _task(
            task_id="lawyer-1",  # same id so it's skipped in sibling check
            role=TaskRole.LAWYER.value,
            status=TaskStatus.IN_PROGRESS.value,
        )
        svc = _make_service(tasks=[lawyer_task])
        svc._tasks.get_task = AsyncMock(return_value=lawyer_task)
        svc._tasks.list_for_verification = AsyncMock(return_value=[lawyer_task, field_task])

        payload = {
            "legal_opinion": "A" * 200,
            "nba_confirmed": True,
            "recommendation": "APPROVE",
            "declaration_signed": True,
        }
        with pytest.raises(ValidationException, match="other agents must submit"):
            await svc.submit("lawyer-1", "agent-1", payload)

    async def test_allows_when_all_siblings_submitted(self):
        lawyer_task = _task(
            task_id="lawyer-1",
            role=TaskRole.LAWYER.value,
            status=TaskStatus.IN_PROGRESS.value,
            agent_id="agent-1",
        )
        field_task = _task(
            task_id="field-1",
            role=TaskRole.FIELD.value,
            status=TaskStatus.SUBMITTED.value,
        )
        submitted_lawyer = _task(
            task_id="lawyer-1",
            role=TaskRole.LAWYER.value,
            status=TaskStatus.SUBMITTED.value,
        )
        svc = _make_service(tasks=[lawyer_task], evidence_gps_count=5)
        svc._tasks.get_task = AsyncMock(side_effect=[lawyer_task, submitted_lawyer])
        svc._tasks.list_for_verification = AsyncMock(
            side_effect=[
                [lawyer_task, field_task],   # for gate check during submit
                [submitted_lawyer, field_task],  # for state derivation
            ]
        )

        payload = {
            "legal_opinion": "A" * 200,
            "nba_confirmed": True,
            "recommendation": "APPROVE",
            "declaration_signed": True,
        }
        result = await svc.submit("lawyer-1", "agent-1", payload)
        # Should reach submission without raising
        assert result.status == TaskStatus.SUBMITTED


# ── trust elevation ───────────────────────────────────────────────────────────

class TestTrustElevation:
    async def test_first_submission_elevates_trust(self):
        field_task = _task(
            task_id="f-1",
            role=TaskRole.FIELD.value,
            status=TaskStatus.IN_PROGRESS.value,
            agent_id="agent-1",
        )
        submitted_task = _task(
            task_id="f-1",
            role=TaskRole.FIELD.value,
            status=TaskStatus.SUBMITTED.value,
            agent_id="agent-1",
        )
        svc = _make_service(tasks=[field_task], evidence_gps_count=5)
        svc._tasks.get_task = AsyncMock(side_effect=[field_task, submitted_task])
        svc._tasks.list_for_verification = AsyncMock(return_value=[submitted_task])

        payload = {
            "access_confirmed": True,
            "declaration_signed": True,
        }
        await svc.submit("f-1", "agent-1", payload)
        svc._users.update.assert_awaited()


# ── state derivation ──────────────────────────────────────────────────────────

class TestStateDeriv:
    async def test_all_approved_sets_under_review(self):
        # All tasks APPROVED → hand off to admin for report review (S28).
        # COMPLETED is set exclusively by ReleaseService.release() (S31).
        tasks = [
            _task("t1", status=TaskStatus.APPROVED.value),
            _task("t2", status=TaskStatus.APPROVED.value),
        ]
        svc = _make_service(tasks=tasks)
        svc._tasks.list_for_verification = AsyncMock(return_value=tasks)
        svc._verifications.get_model.return_value.status = VerificationStatus.IN_PROGRESS.value

        await svc._derive_and_update_verification_status("ver-1")
        update_call = svc._verifications.update.call_args[0][1]
        assert update_call.status == VerificationStatus.UNDER_REVIEW

    async def test_any_active_sets_in_progress(self):
        tasks = [
            _task("t1", status=TaskStatus.ACCEPTED.value),
            _task("t2", status=TaskStatus.PENDING.value),
        ]
        svc = _make_service(tasks=tasks)
        svc._tasks.list_for_verification = AsyncMock(return_value=tasks)
        svc._verifications.get_model.return_value.status = VerificationStatus.PAID.value

        await svc._derive_and_update_verification_status("ver-1")
        update_call = svc._verifications.update.call_args[0][1]
        assert update_call.status == VerificationStatus.IN_PROGRESS

    async def test_all_settled_any_submitted_sets_under_review(self):
        tasks = [
            _task("t1", status=TaskStatus.SUBMITTED.value),
            _task("t2", status=TaskStatus.APPROVED.value),
        ]
        svc = _make_service(tasks=tasks)
        svc._tasks.list_for_verification = AsyncMock(return_value=tasks)
        svc._verifications.get_model.return_value.status = VerificationStatus.IN_PROGRESS.value

        await svc._derive_and_update_verification_status("ver-1")
        update_call = svc._verifications.update.call_args[0][1]
        assert update_call.status == VerificationStatus.UNDER_REVIEW

    async def test_all_pending_does_not_change_verification(self):
        tasks = [_task("t1", status=TaskStatus.PENDING.value)]
        svc = _make_service(tasks=tasks)
        svc._tasks.list_for_verification = AsyncMock(return_value=tasks)

        await svc._derive_and_update_verification_status("ver-1")
        svc._verifications.update.assert_not_awaited()
