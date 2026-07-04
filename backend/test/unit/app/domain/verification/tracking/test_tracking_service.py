"""CustomerTrackingService (§9): the tracking snapshot projection, the first-name-only
API guarantee (§9.5 exit criterion), interim reassurance gating (§9.3), and the
review-approved-only evidence feed (§9.4 / D17). Deps mocked, no DB."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, TaskState, VerificationStatus, VerificationTier
from main.app.domain.verification.tracking.labels import LAWYER_AWAITING_LABEL
from main.app.domain.verification.tracking.service import CustomerTrackingService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx


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


def _task(role, state=TaskState.SUBMITTED, review=None, agent=None, note=None):
    return SimpleNamespace(
        id=f"task-{role.value}", verification_id="v-1", role=role.value, state=state.value,
        assigned_agent_id=agent, review_decision=review, review_quality=100, interim_note=note,
        submitted_at=Utils.datetime_now(), approved_at=Utils.datetime_now(),
    )


def _verification(tier=VerificationTier.STANDARD, status=VerificationStatus.IN_PROGRESS):
    now = Utils.datetime_now()
    return SimpleNamespace(
        id="v-1", vid="VP-ABC123", tier=tier.value, status=status.value,
        property_id="p-1", paused=False, paid_at=now,
        sla_due_date=(now + timedelta(days=10)).date(),
    )


def _service(verification, tasks, evidence=None):
    svc = object.__new__(CustomerTrackingService)
    svc._verifications = MagicMock()
    svc._tasks = MagicMock()
    svc._evidence = MagicMock()
    svc._users = MagicMock()
    svc._agent_profiles = MagicMock()
    svc._properties = MagicMock()
    svc._audit = MagicMock()

    svc._verifications.get_owned = AsyncMock(return_value=verification)
    svc._tasks.list_for_verification = AsyncMock(return_value=list(tasks))
    svc._evidence.list_for_verification = AsyncMock(return_value=list(evidence or []))
    svc._evidence.presigned_url = AsyncMock(return_value="stub-storage://bucket/key")
    # A user with more than the safe fields — the DTO must not leak the rest.
    svc._users.get_model = AsyncMock(return_value=SimpleNamespace(
        first_name="Ada", avatar_url="http://x/a.png",
        last_name="Okoro", email="ada@example.com", phone="+2348000000000",
    ))
    svc._agent_profiles.get_by_user_id = AsyncMock(return_value=SimpleNamespace(
        approved_roles=[AgentRole.REGISTRY.value]))
    svc._properties.get_model = AsyncMock(return_value=SimpleNamespace(address="12 Lekki Rd"))
    return svc


class TestSnapshot:
    async def test_labels_progress_and_steps(self):
        tasks = [
            _task(AgentRole.REGISTRY, review="APPROVED", agent="agent-1", note="Clean title"),
            _task(AgentRole.FIELD, state=TaskState.IN_PROGRESS),
            _task(AgentRole.SURVEYOR, state=TaskState.PENDING),
        ]
        svc = _service(_verification(), tasks)
        snap = await svc.get_snapshot("v-1", "cust-1")

        assert snap.status_label == "Verification In Progress"
        assert snap.address == "12 Lekki Rd"
        assert [t.role for t in snap.tasks] == [AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR]
        # REGISTRY submitted → "In Progress" for the customer; one of three settled → 33%.
        assert snap.progress_percent == 33
        assert snap.sla.label == "On track"

    async def test_assigned_agent_exposes_only_safe_fields(self):
        tasks = [_task(AgentRole.REGISTRY, review="APPROVED", agent="agent-1")]
        svc = _service(_verification(), tasks)
        snap = await svc.get_snapshot("v-1", "cust-1")

        assert len(snap.agents) == 1
        agent = snap.agents[0]
        assert agent.first_name == "Ada"
        assert agent.verified is True  # REGISTRY in approved_roles
        keys = agent.model_dump().keys()
        for leaked in ("last_name", "email", "phone", "lastName"):
            assert leaked not in keys

    async def test_interim_milestone_only_after_review_approval(self):
        tasks = [
            _task(AgentRole.REGISTRY, review="APPROVED", note="Title matches seller"),
            _task(AgentRole.FIELD, state=TaskState.SUBMITTED, review=None),  # reviewed=no
        ]
        svc = _service(_verification(), tasks)
        snap = await svc.get_snapshot("v-1", "cust-1")

        assert len(snap.interim_milestones) == 1
        m = snap.interim_milestones[0]
        assert m.role == AgentRole.REGISTRY
        assert "so far" in m.message.lower()  # provisional framing (§9.3)
        assert m.note == "Title matches seller"

    async def test_lawyer_row_awaiting_when_locked(self):
        # Premium, only REGISTRY submitted → Lawyer not yet instantiated + blocked.
        tasks = [
            _task(AgentRole.REGISTRY, state=TaskState.SUBMITTED),
            _task(AgentRole.FIELD, state=TaskState.IN_PROGRESS),
            _task(AgentRole.SURVEYOR, state=TaskState.IN_PROGRESS),
        ]
        svc = _service(_verification(tier=VerificationTier.PREMIUM), tasks)
        snap = await svc.get_snapshot("v-1", "cust-1")

        lawyer = next(t for t in snap.tasks if t.role == AgentRole.LAWYER)
        assert lawyer.locked is True
        assert lawyer.state_label == LAWYER_AWAITING_LABEL


class TestEvidenceGate:
    async def test_evidence_feed_only_from_review_approved_tasks(self):
        tasks = [
            _task(AgentRole.REGISTRY, review="APPROVED"),   # visible
            _task(AgentRole.FIELD, state=TaskState.SUBMITTED, review=None),  # hidden
        ]
        evidence = [
            SimpleNamespace(id="e-reg", task_id="task-REGISTRY", kind="PHOTO", mime_type="image/jpeg",
                            content_sha256="a" * 64, gps_latitude=6.4, gps_longitude=3.4,
                            captured_at=Utils.datetime_now(), uploaded_at=Utils.datetime_now()),
            SimpleNamespace(id="e-field", task_id="task-FIELD", kind="PHOTO", mime_type="image/jpeg",
                            content_sha256="b" * 64, gps_latitude=None, gps_longitude=None,
                            captured_at=None, uploaded_at=Utils.datetime_now()),
        ]
        svc = _service(_verification(), tasks, evidence)
        page = await svc.list_evidence("v-1", "cust-1", page=0, page_size=10)

        assert page.meta.total == 1
        assert page.items[0].id == "e-reg"
        assert page.items[0].role == AgentRole.REGISTRY
        assert page.items[0].url  # presigned
