"""Unit tests for TrackingService (S32)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.portal.tracking import TrackingService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ForbiddenException, ResourceNotFoundException


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


def _ver(customer_id: str = "cust-1", status: str = "IN_PROGRESS", tier: str = "BASIC"):
    v = MagicMock()
    v.id = "ver-id-1"
    v.vid = "VID-001"
    v.customer_id = customer_id
    v.status = status
    v.tier = tier
    v.paid_at = datetime.now(timezone.utc)
    v.trust_score = None
    v.property_id = None
    return v


def _task(role: str, agent_id: str | None = None):
    t = MagicMock()
    t.role = role
    t.agent_id = agent_id
    t.status = "IN_PROGRESS"
    return t


def _user(first_name: str = "John"):
    u = MagicMock()
    u.first_name = first_name
    return u


def _make_service(ver=None, tasks=None, user=None):
    ver_repo = MagicMock()
    ver_repo.get_by_vid = AsyncMock(return_value=ver or _ver())

    task_repo = MagicMock()
    task_repo.list_for_verification = AsyncMock(return_value=tasks or [])

    user_repo = MagicMock()
    user_repo.get = AsyncMock(return_value=user or _user())

    svc = TrackingService(
        verification_repo=ver_repo,
        task_repo=task_repo,
        user_repo=user_repo,
    )
    return svc, ver_repo, task_repo, user_repo


class TestGetTracking:
    async def test_returns_correct_label_for_in_progress(self):
        svc, _, _, _ = _make_service(ver=_ver(status="IN_PROGRESS"))
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert result.status == "IN_PROGRESS"
        assert "agent" in result.status_detail.lower() or "progress" in result.status_detail.lower()

    async def test_progress_pct_completed_is_100(self):
        svc, _, _, _ = _make_service(ver=_ver(status="COMPLETED"))
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert result.progress_pct == 100

    async def test_progress_pct_paid_is_20(self):
        svc, _, _, _ = _make_service(ver=_ver(status="PAID"))
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert result.progress_pct == 20

    async def test_ownership_check_blocks_other_customer(self):
        svc, _, _, _ = _make_service(ver=_ver(customer_id="cust-1"))
        with pytest.raises(ForbiddenException):
            await svc.get_tracking("VID-001", customer_id="cust-OTHER")

    async def test_raises_if_not_found(self):
        svc, ver_repo, _, _ = _make_service()
        ver_repo.get_by_vid = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.get_tracking("VID-MISSING", customer_id="cust-1")

    async def test_agent_list_shows_first_name_only(self):
        tasks = [_task("FIELD", agent_id="agent-1")]
        svc, _, _, user_repo = _make_service(
            tasks=tasks,
            user=_user(first_name="Emeka"),
        )
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert len(result.assigned_agents) == 1
        assert result.assigned_agents[0].first_name == "Emeka"
        assert result.assigned_agents[0].role == "FIELD"

    async def test_agent_response_has_no_last_name(self):
        tasks = [_task("REGISTRY", agent_id="agent-2")]
        svc, _, _, _ = _make_service(tasks=tasks)
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        for agent in result.assigned_agents:
            assert not hasattr(agent, "last_name") or getattr(agent, "last_name", None) is None

    async def test_sla_computed_from_paid_at(self):
        svc, _, _, _ = _make_service(ver=_ver(status="IN_PROGRESS", tier="BASIC"))
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert result.sla is not None
        assert result.sla.target_days == 5

    async def test_no_sla_when_not_paid(self):
        ver = _ver(status="DRAFT")
        ver.paid_at = None
        svc, _, _, _ = _make_service(ver=ver)
        result = await svc.get_tracking("VID-001", customer_id="cust-1")
        assert result.sla is None
