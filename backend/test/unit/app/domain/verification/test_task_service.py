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
    return SimpleNamespace(
        id="v-1", vid="VP-2026-0001", status=status.value, tier=tier.value,
        customer_id="cust-1",
    )


def _make_service(verification, tasks):
    svc = object.__new__(VerificationTaskService)
    svc._task_repo = MagicMock()
    svc._verification_repo = MagicMock()
    svc._evidence = MagicMock()
    svc._user_service = MagicMock()
    svc._audit = MagicMock()

    svc._verification_repo.get_model = AsyncMock(return_value=verification)
    svc._verification_repo.update = AsyncMock()
    svc._evidence.count_for_task = AsyncMock(return_value=1)
    svc._user_service.upgrade_trust_status_if_eligible = AsyncMock()

    state = {"tasks": list(tasks)}
    svc._task_repo.list_for_verification = AsyncMock(side_effect=lambda vid: list(state["tasks"]))

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

    svc._task_repo.get_by_role = AsyncMock(side_effect=_get_by_role)
    svc._task_repo.create_return_model = AsyncMock(side_effect=_create)
    svc._task_repo.update = AsyncMock(side_effect=_update)
    svc._task_repo.get_model = AsyncMock(side_effect=_get_model)
    svc._task_repo.count_active_for_agent = AsyncMock(return_value=0)
    svc._task_repo.list_accept_deadline_expired = AsyncMock(return_value=[])
    svc._task_repo.list_pool_expired = AsyncMock(return_value=[])
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


def _capture_events(monkeypatch):
    """Every event one call publishes, from both modules that emit during derivation."""
    import main.app.domain.verification.status_events as status_events_mod
    import main.app.domain.verification.task.service as task_mod

    published = []
    recorder = AsyncMock(side_effect=lambda e: published.append(e))
    monkeypatch.setattr(task_mod, "publish_domain_event", recorder)
    monkeypatch.setattr(status_events_mod, "publish_domain_event", recorder)
    return published


class TestAssign:
    async def test_first_assignment_derives_in_progress(self):
        svc = _make_service(_verification(status=VerificationStatus.PAID), [_task(AgentRole.REGISTRY)])
        await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")
        svc._verification_repo.update.assert_awaited()
        derived = svc._verification_repo.update.await_args.args[1]
        assert derived.status == VerificationStatus.IN_PROGRESS.value

    async def test_first_assignment_announces_the_start_milestone(self, monkeypatch):
        """§7.6.2's "verification started" (D66): the first agent picking the case up is
        the moment, and this is the only site that produces it — a rejection needs a
        SUBMITTED task, so the review half can only ever be work *continuing*."""
        from main.app.core.events.events import EventType

        published = _capture_events(monkeypatch)
        svc = _make_service(
            _verification(status=VerificationStatus.PAID),
            [_task(AgentRole.REGISTRY), _task(AgentRole.FIELD)],
        )
        await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")

        started = [e for e in published if e.type == EventType.VERIFICATION_STARTED]
        assert len(started) == 1
        assert started[0].recipient_user_ids == ("cust-1",)
        assert started[0].data["vid"] == "VP-2026-0001"

    async def test_assigning_the_next_agent_does_not_announce_it_again(self, monkeypatch):
        """The defect the live drive-through caught. `derive_status` has no memory, so a
        case drops back to PAID when a task is submitted and re-enters IN_PROGRESS when
        the next agent is assigned — three roles meant three "we've started" messages.

        A task already submitted is what tells the two apart, and it needs no column to
        record.
        """
        from main.app.core.events.events import EventType

        published = _capture_events(monkeypatch)
        svc = _make_service(
            _verification(status=VerificationStatus.PAID),
            [_task(AgentRole.REGISTRY, TaskState.SUBMITTED, agent="agent-1"),
             _task(AgentRole.FIELD)],
        )
        await svc.assign("v-1", AgentRole.FIELD, "agent-2", "admin-1")

        assert not [e for e in published if e.type == EventType.VERIFICATION_STARTED]

    async def test_sets_assigned_state_and_agent(self):
        svc = _make_service(_verification(), [_task(AgentRole.REGISTRY)])
        task = await svc.assign("v-1", AgentRole.REGISTRY, "agent-1", "admin-1")
        assert task.state == TaskState.ASSIGNED.value
        assert task.assigned_agent_id == "agent-1"
        assert task.assignment_mode == TaskAssignmentMode.MANUAL.value

    async def test_capacity_cap_rejects(self, monkeypatch):
        monkeypatch.setattr(settings, "AGENT_MAX_ACTIVE_TASKS", 2)
        svc = _make_service(_verification(), [_task(AgentRole.REGISTRY)])
        svc._task_repo.count_active_for_agent = AsyncMock(return_value=2)
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
        svc._task_repo.list_accept_deadline_expired = AsyncMock(return_value=[stale])
        count = await svc.sweep_no_show()
        assert count == 1
        assert stale.state == TaskState.PENDING.value
        assert stale.assigned_agent_id is None

    async def test_pool_starvation_removes_from_pool(self):
        stale = _task(AgentRole.FIELD, TaskState.PENDING, in_pool=True)
        svc = _make_service(_verification(), [stale])
        svc._task_repo.list_pool_expired = AsyncMock(return_value=[stale])
        count = await svc.sweep_pool_starvation()
        assert count == 1
        assert stale.in_pool is False


class TestAgentDashboardSummary:
    def _summary_service(self, state_counts):
        svc = object.__new__(VerificationTaskService)
        svc._task_repo = MagicMock()
        svc._task_repo.count_by_state_for_agent = AsyncMock(return_value=state_counts)
        svc._task_repo.count_pool_pending = AsyncMock(return_value=6)
        return svc

    async def test_agent_summary_rolls_up_states(self):
        counts = {
            TaskState.ASSIGNED.value: 1,
            TaskState.ACCEPTED.value: 2,
            TaskState.IN_PROGRESS.value: 1,
            TaskState.REJECTED.value: 1,
            TaskState.SUBMITTED.value: 3,
            TaskState.APPROVED.value: 5,
        }
        svc = self._summary_service(counts)
        dto = await svc.agent_summary("agent-1")

        assert dto.assigned == 1
        assert dto.active == 4          # ACCEPTED + IN_PROGRESS + REJECTED
        assert dto.submitted == 3
        assert dto.approved == 5
        assert dto.total == 13
        assert dto.state_counts[TaskState.SUBMITTED] == 3

    async def test_count_pool_pending_delegates(self):
        svc = self._summary_service({})
        assert await svc.count_pool_pending() == 6
