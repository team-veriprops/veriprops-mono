"""ReviewService (§8): approve/reject, the explicit release gate (flip→APPROVED +
report + commissions + COMPLETED), reopen, and fail+refund. Deps mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, TaskState, VerificationStatus, VerificationTier
from main.app.domain.verification.review.service import ReviewService
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


def _task(role, state=TaskState.SUBMITTED, review=None, payload=None, agent="agent-1"):
    return SimpleNamespace(
        id=f"task-{role.value}", verification_id="v-1", role=role.value,
        tier=VerificationTier.STANDARD.value, state=state.value,
        assigned_agent_id=agent, review_decision=review, review_quality=100,
        submission_payload=payload or {"ok": True}, rejection_reason=None,
        in_pool=False, assignment_mode=None, decline_count=0,
        submitted_at=None, approved_at=None,
    )


def _verification(status=VerificationStatus.UNDER_REVIEW, tier=VerificationTier.STANDARD, price=1000000):
    return SimpleNamespace(id="v-1", status=status.value, tier=tier.value, price_locked_minor=price)


def _make_service(verification, tasks):
    svc = object.__new__(ReviewService)
    svc._tasks = MagicMock()
    svc._verification_repo = MagicMock()
    svc._reports = MagicMock()
    svc._weights = MagicMock()
    svc._commissions = MagicMock()
    svc._payments = MagicMock()
    svc._audit = MagicMock()

    state = {"tasks": list(tasks), "verification": verification}

    async def _list(vid):
        return list(state["tasks"])

    async def _by_role(vid, role):
        return next((t for t in state["tasks"] if t.role == role), None)

    async def _get_model(tid):
        return next((t for t in state["tasks"] if t.id == tid), None)

    async def _update(tid, dto):
        t = next((t for t in state["tasks"] if t.id == tid), None)
        if t:
            for f, v in dto.model_dump(exclude_none=True).items():
                setattr(t, f, v)
        return t

    svc._tasks.list_for_verification = AsyncMock(side_effect=_list)
    svc._tasks.get_by_role = AsyncMock(side_effect=_by_role)
    svc._tasks.get_model = AsyncMock(side_effect=_get_model)
    svc._tasks.update = AsyncMock(side_effect=_update)

    svc._verification_repo.get_model = AsyncMock(return_value=verification)
    svc._verification_repo.update = AsyncMock()

    svc._weights.compute_composite = AsyncMock(return_value=95)
    svc._weights.list_for_tier = AsyncMock(return_value=[
        SimpleNamespace(role=AgentRole.REGISTRY.value, weight_percent=40),
        SimpleNamespace(role=AgentRole.FIELD.value, weight_percent=30),
        SimpleNamespace(role=AgentRole.SURVEYOR.value, weight_percent=30),
    ])
    svc._commissions.accrue = AsyncMock()
    svc._reports.release = AsyncMock(return_value=SimpleNamespace(id="rep-1"))
    svc._reports.get_released = AsyncMock(return_value=None)
    svc._reports.supersede_current = AsyncMock()
    svc._payments.refund = AsyncMock(return_value=1000000)
    svc._state = state
    return svc


def _standard_tasks(review="APPROVED", state=TaskState.SUBMITTED):
    return [_task(r, state=state, review=review) for r in
            (AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR)]


class TestApproveReject:
    async def test_approve_records_intent_without_state_change(self):
        tasks = _standard_tasks(review=None)
        svc = _make_service(_verification(), tasks)
        await svc.approve_task("v-1", AgentRole.REGISTRY, 90, "admin-1")
        reg = next(t for t in tasks if t.role == AgentRole.REGISTRY.value)
        assert reg.review_decision == "APPROVED"
        assert reg.review_quality == 90
        assert reg.state == TaskState.SUBMITTED.value  # unchanged until release

    async def test_approve_rejects_non_submitted(self):
        tasks = [_task(AgentRole.REGISTRY, state=TaskState.IN_PROGRESS)]
        svc = _make_service(_verification(), tasks)
        with pytest.raises(InvalidResourceStateException):
            await svc.approve_task("v-1", AgentRole.REGISTRY, 100, "admin-1")

    async def test_reject_sends_task_to_rework(self):
        tasks = _standard_tasks(review=None)
        svc = _make_service(_verification(), tasks)
        await svc.reject_task("v-1", AgentRole.FIELD, "blurry photos", "admin-1")
        field = next(t for t in tasks if t.role == AgentRole.FIELD.value)
        assert field.state == TaskState.REJECTED.value
        assert field.rejection_reason == "blurry photos"
        # derive → IN_PROGRESS persisted
        assert svc._verification_repo.update.await_args.args[1].status == VerificationStatus.IN_PROGRESS.value


class TestRelease:
    async def test_happy_path_flips_approved_and_completes(self):
        tasks = _standard_tasks(review="APPROVED")
        svc = _make_service(_verification(), tasks)
        ctx = await svc.release("v-1", "admin-1", reason="looks good")
        assert all(t.state == TaskState.APPROVED.value for t in tasks)
        svc._reports.release.assert_awaited_once()
        assert svc._commissions.accrue.await_count == 3
        assert ctx.projected_trust_score == 95
        # derive → COMPLETED
        assert svc._verification_repo.update.await_args.args[1].status == VerificationStatus.COMPLETED.value

    async def test_blocks_when_not_all_review_approved(self):
        tasks = _standard_tasks(review="APPROVED")
        tasks[1].review_decision = None
        svc = _make_service(_verification(), tasks)
        with pytest.raises(ValidationException):
            await svc.release("v-1", "admin-1")

    async def test_blocks_when_not_under_review(self):
        svc = _make_service(_verification(status=VerificationStatus.IN_PROGRESS), _standard_tasks())
        with pytest.raises(InvalidResourceStateException):
            await svc.release("v-1", "admin-1")

    async def test_blocks_on_high_conflict(self):
        tasks = [
            _task(AgentRole.REGISTRY, review="APPROVED",
                  payload={"title_search_result": "encumbrance found", "encumbrances": ["lien"]}),
            _task(AgentRole.FIELD, review="APPROVED"),
            _task(AgentRole.SURVEYOR, review="APPROVED"),
        ]
        # Premium tier so a Lawyer can conflict; use premium verification + 4 tasks.
        tasks.append(_task(AgentRole.LAWYER, review="APPROVED",
                           payload={"legal_opinion": "ok", "risk_level": "low", "recommendation": "proceed"}))
        for t in tasks:
            t.tier = VerificationTier.PREMIUM.value
        svc = _make_service(_verification(tier=VerificationTier.PREMIUM), tasks)
        with pytest.raises(ValidationException):
            await svc.release("v-1", "admin-1")


class TestReopenFail:
    async def test_reopen_approved_task(self):
        tasks = _standard_tasks(review="APPROVED", state=TaskState.APPROVED)
        svc = _make_service(_verification(status=VerificationStatus.COMPLETED), tasks)
        await svc.reopen_task("v-1", AgentRole.REGISTRY, "admin-1")
        reg = next(t for t in tasks if t.role == AgentRole.REGISTRY.value)
        assert reg.state == TaskState.IN_PROGRESS.value
        svc._reports.supersede_current.assert_awaited_once()
        assert svc._verification_repo.update.await_args.args[1].status == VerificationStatus.IN_PROGRESS.value

    async def test_fail_marks_failed_and_refunds(self):
        svc = _make_service(_verification(status=VerificationStatus.UNDER_REVIEW), _standard_tasks())
        await svc.fail("v-1", "fraud detected", "admin-1")
        svc._payments.refund.assert_awaited_once()
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list]
        assert VerificationStatus.FAILED.value in statuses
