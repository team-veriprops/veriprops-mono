"""VerificationTaskService — instantiation (§4.2 locks), assignment (§6), derivation
owner integration (§4.1), and timeout sweeps (§7.2). Repos mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.verification.task.models import TaskAssignmentMode
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)


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


def _task(role, state=TaskState.PENDING, agent=None, **over):
    base = dict(
        id=f"task-{role.value}",
        verification_id="v-1",
        role=role.value,
        tier=VerificationTier.STANDARD.value,
        state=state.value,
        assigned_agent_id=agent,
        assignment_mode=None,
        in_pool=False,
        decline_count=0,
        pool_expires_at=None,
        accept_deadline_at=None,
        remote_bonus_minor=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _verification(status=VerificationStatus.PAID, tier=VerificationTier.STANDARD):
    return SimpleNamespace(id="v-1", status=status.value, tier=tier.value)


def _make_service(verification, tasks):
    svc = object.__new__(VerificationTaskService)
    svc._repo = MagicMock()
    svc._verification_repo = MagicMock()
    svc._evidence = MagicMock()
    svc._user_service = MagicMock()
    svc._audit = MagicMock()

    svc._verification_repo.get_model = AsyncMock(return_value=verification)
    svc._verification_repo.update = AsyncMock()
    svc._evidence.count_for_task = AsyncMock(return_value=1)
    svc._user_service.upgrade_trust_status_if_eligible = AsyncMock()

    state = {"tasks": list(tasks)}
    svc._repo.list_for_verification = AsyncMock(side_effect=lambda vid: list(state["tasks"]))

    async def _get_by_role(vid, role):
        return next((t for t in state["tasks"] if t.role == role), None)

    async def _create(dto):
        t = _task(dto.role, state=dto.state, tier=dto.tier.value)
        state["tasks"].append(t)
        return t

    async def _update(task_id, dto):
        t = next((t for t in state["tasks"] if t.id == task_id), None)
        if t is not None:
            for f, v in dto.model_dump(exclude_none=True).items():
                setattr(t, f, v)
        return t

    async def _get_model(task_id):
        return next((t for t in state["tasks"] if t.id == task_id), None)

    svc._repo.get_by_role = AsyncMock(side_effect=_get_by_role)
    svc._repo.create_return_model = AsyncMock(side_effect=_create)
    svc._repo.update = AsyncMock(side_effect=_update)
    svc._repo.get_model = AsyncMock(side_effect=_get_model)
    svc._repo.count_active_for_agent = AsyncMock(return_value=0)
    svc._repo.list_accept_deadline_expired = AsyncMock(return_value=[])
    svc._repo.list_pool_expired = AsyncMock(return_value=[])
    svc._state = state
    return svc


class TestInstantiate:
    async def test_creates_tasks_for_all_standard_roles(self):
        svc = _make_service(_verification(tier=VerificationTier.STANDARD), [])
        created = await svc.instantiate_unlocked("v-1")
        roles = {t.role for t in created}
        assert roles == {AgentRole.REGISTRY.value, AgentRole.FIELD.value, AgentRole.SURVEYOR.value}

    async def test_premium_lawyer_locked_until_siblings_submitted(self):
        svc = _make_service(_verification(tier=VerificationTier.PREMIUM), [])
        created = await svc.instantiate_unlocked("v-1")
        assert AgentRole.LAWYER.value not in {t.role for t in created}

    async def test_premium_lawyer_unlocks_when_siblings_submitted(self):
        submitted = [
            _task(AgentRole.REGISTRY, TaskState.SUBMITTED),
            _task(AgentRole.FIELD, TaskState.SUBMITTED),
            _task(AgentRole.SURVEYOR, TaskState.SUBMITTED),
        ]
        svc = _make_service(_verification(tier=VerificationTier.PREMIUM), submitted)
        created = await svc.instantiate_unlocked("v-1")
        assert {t.role for t in created} == {AgentRole.LAWYER.value}

    async def test_idempotent_does_not_duplicate(self):
        existing = [_task(AgentRole.REGISTRY)]
        svc = _make_service(_verification(tier=VerificationTier.BASIC), existing)
        created = await svc.instantiate_unlocked("v-1")
        assert created == []


class TestPrepareForPaid:
    async def test_broadcasts_when_auto_assignment_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTO_ASSIGNMENT_ENABLED", True)
        svc = _make_service(_verification(tier=VerificationTier.BASIC), [])
        await svc.prepare_for_paid("v-1")
        assert any(t.in_pool for t in svc._state["tasks"])

    async def test_no_broadcast_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTO_ASSIGNMENT_ENABLED", False)
        svc = _make_service(_verification(tier=VerificationTier.BASIC), [])
        await svc.prepare_for_paid("v-1")
        assert all(getattr(t, "in_pool", False) is not True for t in svc._state["tasks"])


class TestAssign:
    async def test_first_assignment_derives_in_progress(self):
        svc = _make_service(_verification(status=VerificationStatus.PAID), [_task(AgentRole.REGISTRY)])
        await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")
        svc._verification_repo.update.assert_awaited()
        derived = svc._verification_repo.update.await_args.args[1]
        assert derived.status == VerificationStatus.IN_PROGRESS.value

    async def test_sets_assigned_state_and_agent(self):
        svc = _make_service(_verification(), [_task(AgentRole.REGISTRY)])
        task = await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")
        assert task.state == TaskState.ASSIGNED.value
        assert task.assigned_agent_id == "agent-1"
        assert task.assignment_mode == TaskAssignmentMode.MANUAL.value

    async def test_capacity_cap_rejects(self, monkeypatch):
        monkeypatch.setattr(settings, "AGENT_MAX_ACTIVE_TASKS", 2)
        svc = _make_service(_verification(), [_task(AgentRole.REGISTRY)])
        svc._repo.count_active_for_agent = AsyncMock(return_value=2)
        with pytest.raises(ValidationException):
            await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")

    async def test_reassignment_audits_reassigned(self):
        svc = _make_service(_verification(status=VerificationStatus.IN_PROGRESS),
                            [_task(AgentRole.REGISTRY, TaskState.ASSIGNED, agent="agent-0")])
        await svc.assign("v-1", AgentRole.REGISTRY, "agent-9", "admin-1")
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.TASK_REASSIGNED in actions

    async def test_terminal_verification_rejects(self):
        svc = _make_service(_verification(status=VerificationStatus.CANCELLED), [])
        with pytest.raises(InvalidResourceStateException):
            await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")

    async def test_locked_lawyer_rejects_when_no_task(self):
        svc = _make_service(_verification(status=VerificationStatus.PAID, tier=VerificationTier.PREMIUM), [])
        with pytest.raises(InvalidResourceStateException):
            await svc.assign("v-1", AgentRole.LAWYER, "agent-1", "admin-1")


def _valid_payload(role):
    return {
        AgentRole.REGISTRY: {"registered_owner": "A", "title_search_result": "clean", "search_reference": "R1"},
        AgentRole.FIELD: {"occupancy_status": "vacant", "physical_condition": "good"},
        AgentRole.SURVEYOR: {"area_sqm": 500, "beacon_status": "intact"},
        AgentRole.LAWYER: {"legal_opinion": "sound", "risk_level": "low", "recommendation": "proceed"},
    }[role]


class TestAgentExecution:
    async def test_accept_from_pool_first_wins(self):
        pooled = _task(AgentRole.FIELD, TaskState.PENDING, in_pool=True)
        svc = _make_service(_verification(), [pooled])
        task = await svc.accept(pooled.id, "agent-1")
        assert task.state == TaskState.ACCEPTED.value
        assert task.assigned_agent_id == "agent-1"

    async def test_accept_rejects_already_taken_pool_task(self):
        taken = _task(AgentRole.FIELD, TaskState.ACCEPTED, agent="agent-0", in_pool=False)
        svc = _make_service(_verification(), [taken])
        with pytest.raises(ValidationException):
            await svc.accept(taken.id, "agent-1")  # not owner, not pool

    async def test_accept_manual_only_assigned_agent(self):
        assigned = _task(AgentRole.REGISTRY, TaskState.ASSIGNED, agent="agent-0")
        svc = _make_service(_verification(), [assigned])
        with pytest.raises(ValidationException):
            await svc.accept(assigned.id, "agent-9")

    async def test_decline_returns_to_pool_and_clears_agent(self):
        mine = _task(AgentRole.FIELD, TaskState.ACCEPTED, agent="agent-1")
        svc = _make_service(_verification(), [mine])
        task = await svc.decline(mine.id, "agent-1", reason="too far")
        assert task.state == TaskState.PENDING.value
        assert task.in_pool is True
        assert task.assigned_agent_id is None
        assert task.decline_count == 1

    async def test_start_moves_to_in_progress(self):
        mine = _task(AgentRole.FIELD, TaskState.ACCEPTED, agent="agent-1")
        svc = _make_service(_verification(), [mine])
        task = await svc.start(mine.id, "agent-1")
        assert task.state == TaskState.IN_PROGRESS.value

    async def test_submit_requires_evidence(self):
        mine = _task(AgentRole.FIELD, TaskState.IN_PROGRESS, agent="agent-1")
        svc = _make_service(_verification(), [mine])
        svc._evidence.count_for_task = AsyncMock(return_value=0)
        with pytest.raises(ValidationException):
            await svc.submit(mine.id, "agent-1", _valid_payload(AgentRole.FIELD))

    async def test_submit_validates_role_form(self):
        mine = _task(AgentRole.SURVEYOR, TaskState.IN_PROGRESS, agent="agent-1")
        svc = _make_service(_verification(), [mine])
        with pytest.raises(ValidationException):
            await svc.submit(mine.id, "agent-1", {"area_sqm": 500})  # missing beacon_status

    async def test_submit_transitions_and_upgrades_trust(self):
        mine = _task(AgentRole.FIELD, TaskState.IN_PROGRESS, agent="agent-1")
        svc = _make_service(_verification(status=VerificationStatus.IN_PROGRESS), [mine])
        task = await svc.submit(mine.id, "agent-1", _valid_payload(AgentRole.FIELD))
        assert task.state == TaskState.SUBMITTED.value
        svc._user_service.upgrade_trust_status_if_eligible.assert_awaited_once()

    async def test_submit_not_owner_rejected(self):
        mine = _task(AgentRole.FIELD, TaskState.IN_PROGRESS, agent="agent-1")
        svc = _make_service(_verification(), [mine])
        with pytest.raises(ValidationException):
            await svc.submit(mine.id, "agent-9", _valid_payload(AgentRole.FIELD))


class TestSweeps:
    async def test_no_show_returns_to_pending(self):
        stale = _task(AgentRole.REGISTRY, TaskState.ASSIGNED, agent="agent-1")
        svc = _make_service(_verification(status=VerificationStatus.IN_PROGRESS), [stale])
        svc._repo.list_accept_deadline_expired = AsyncMock(return_value=[stale])
        count = await svc.sweep_no_show()
        assert count == 1
        assert stale.state == TaskState.PENDING.value
        assert stale.assigned_agent_id is None

    async def test_pool_starvation_removes_from_pool(self):
        stale = _task(AgentRole.FIELD, TaskState.PENDING, in_pool=True)
        svc = _make_service(_verification(), [stale])
        svc._repo.list_pool_expired = AsyncMock(return_value=[stale])
        count = await svc.sweep_pool_starvation()
        assert count == 1
        assert stale.in_pool is False
