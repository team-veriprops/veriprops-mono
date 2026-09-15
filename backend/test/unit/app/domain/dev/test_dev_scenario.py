"""`/dev/scenario` contract — the lifecycle builder browser specs start from.

The builder is only worth trusting if it stops exactly where it says and walks the same
path a real case does. These tests pin the ordering against mocked services: which actions
each stage performs, that nothing beyond the requested stage happens, and that a role locked
behind its siblings (LAWYER on PREMIUM) is never touched before they have submitted.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.dev.scenario import (
    ROLE_SUBMISSIONS,
    BuildScenarioDto,
    DevScenarioService,
    ScenarioAccountDto,
    ScenarioStage,
    stage_reached,
)
from main.app.domain.verification.task.validator import validate_submission


def _service(calls: list[str], tier: VerificationTier, final_status: VerificationStatus):
    """A scenario service whose collaborators record every lifecycle call in order."""
    svc = object.__new__(DevScenarioService)

    def recorder(name, result=None):
        async def _call(*args, **_kwargs):
            detail = args[1].value if name in {"assign", "approve_task"} else ""
            calls.append(f"{name}:{detail}" if detail else name)
            return result(*args) if callable(result) else result
        return AsyncMock(side_effect=_call)

    task_ids = {}

    def assigned_task(_vid, role, *_rest):
        task_ids[role] = SimpleNamespace(id=f"task-{role.value.lower()}")
        return task_ids[role]

    svc._verification_service = SimpleNamespace(
        create_draft=recorder("create_draft", SimpleNamespace(id="ab" * 16, vid="VP-2026-TEST")),
        submit=recorder("submit"),
        get_owned=recorder("get_owned", SimpleNamespace(status=final_status.value)),
    )
    svc._payment_service = SimpleNamespace(
        initiate=recorder("initiate", SimpleNamespace(tx_ref="VP-TX")),
        handle_webhook=recorder("handle_webhook", True),
    )
    svc._verification_task_service = SimpleNamespace(
        assign=recorder("assign", assigned_task),
        accept=recorder("accept"),
        start=recorder("start"),
        add_evidence=recorder("add_evidence"),
        submit=AsyncMock(side_effect=lambda task_id, *_: calls.append(f"task_submit:{task_id}")),
    )
    svc._review_service = SimpleNamespace(
        approve_task=recorder("approve_task"),
        release=recorder("release"),
    )

    async def run_inline(action):
        return await action()

    async def people(_tier):
        return (
            ScenarioAccountDto(id="customer-id", email="c@veriprops.io", password="x"),
            {role: ScenarioAccountDto(id=f"agent-{role.value}", email="a@veriprops.io", password="x")
             for role in roles_for_tier(tier)},
        )

    svc._step = run_inline
    svc._create_people = people
    svc._super_admin_id = AsyncMock(return_value="admin-id")
    svc._verification_terms_version = AsyncMock(return_value="1.0.0")
    return svc


async def _build(stage: ScenarioStage, tier=VerificationTier.STANDARD,
                 status=VerificationStatus.DRAFT):
    calls: list[str] = []
    svc = _service(calls, tier, status)
    result = await svc.build(BuildScenarioDto(stage=stage, tier=tier))
    return calls, result


class TestStageOrdering:
    def test_stages_are_cumulative(self):
        assert stage_reached(ScenarioStage.RELEASED, ScenarioStage.PAID)
        assert stage_reached(ScenarioStage.PAID, ScenarioStage.PAID)
        assert not stage_reached(ScenarioStage.PAID, ScenarioStage.ASSIGNED)

    async def test_draft_stops_before_submission(self):
        calls, result = await _build(ScenarioStage.DRAFT)
        assert calls == ["create_draft", "get_owned"]
        assert result.vid == "VP-2026-TEST" and result.status == VerificationStatus.DRAFT

    async def test_paid_confirms_payment_but_assigns_nobody(self):
        calls, result = await _build(ScenarioStage.PAID, status=VerificationStatus.PAID)
        assert calls == ["create_draft", "submit", "initiate", "handle_webhook", "get_owned"]
        assert all(agent.task_id is None for agent in result.agents.values())

    async def test_assigned_stops_before_agents_act(self):
        calls, result = await _build(ScenarioStage.ASSIGNED, status=VerificationStatus.IN_PROGRESS)
        roles = roles_for_tier(VerificationTier.STANDARD)
        assert [c for c in calls if c.startswith("assign")] == [f"assign:{r.value}" for r in roles]
        assert "accept" not in calls and "release" not in calls
        assert {role: agent.task_id for role, agent in result.agents.items()} == {
            role: f"task-{role.value.lower()}" for role in roles
        }

    async def test_released_walks_every_step_once(self):
        calls, _ = await _build(ScenarioStage.RELEASED, status=VerificationStatus.COMPLETED)
        roles = roles_for_tier(VerificationTier.STANDARD)
        assert calls.count("accept") == len(roles)
        assert calls.count("add_evidence") == len(roles)
        assert len([c for c in calls if c.startswith("task_submit")]) == len(roles)
        assert len([c for c in calls if c.startswith("approve_task")]) == len(roles)
        assert calls.count("release") == 1
        # Release is the final mutation — approving after it would be a different case.
        assert calls.index("release") > max(i for i, c in enumerate(calls) if c.startswith("approve_task"))


class TestDependencyWaves:
    async def test_premium_lawyer_is_assigned_only_after_its_siblings_submit(self):
        calls, _ = await _build(
            ScenarioStage.UNDER_REVIEW, tier=VerificationTier.PREMIUM,
            status=VerificationStatus.UNDER_REVIEW,
        )
        lawyer_assigned = calls.index(f"assign:{AgentRole.LAWYER.value}")
        sibling_submits = [i for i, c in enumerate(calls)
                           if c.startswith("task_submit") and "lawyer" not in c]
        assert sibling_submits and max(sibling_submits) < lawyer_assigned

    async def test_premium_in_progress_leaves_the_locked_lawyer_unassigned(self):
        calls, result = await _build(
            ScenarioStage.IN_PROGRESS, tier=VerificationTier.PREMIUM,
            status=VerificationStatus.IN_PROGRESS,
        )
        assert f"assign:{AgentRole.LAWYER.value}" not in calls
        assert result.agents[AgentRole.LAWYER].task_id is None


@pytest.mark.parametrize("role", list(AgentRole))
def test_every_role_submission_passes_the_real_validator(role):
    """A payload that drifted from `task/validator.py` would fail every scenario past
    IN_PROGRESS on a live stack while these mocked tests stayed green."""
    validate_submission(role, ROLE_SUBMISSIONS[role])
