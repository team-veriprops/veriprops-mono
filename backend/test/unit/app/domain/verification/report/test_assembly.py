"""Unit tests for ReportAssemblyService (S35)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.report.assembly import ReportAssemblyService
from main.app.domain.verification.task.models import TaskRole
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
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


def _ver(customer_id: str = "cust-1", status: str = VerificationStatus.COMPLETED.value, tier: str = "BASIC"):
    v = MagicMock()
    v.id = "ver-id-1"
    v.vid = "VID-001"
    v.customer_id = customer_id
    v.status = status
    v.tier = tier
    v.completed_at = datetime.now(timezone.utc)
    v.trust_score = Decimal("85.00")
    return v


def _task(role: str, payload: dict):
    t = MagicMock()
    t.id = f"task-{role}"
    t.role = role
    t.draft_payload = json.dumps(payload)
    return t


def _make_service(ver=None, tasks=None, has_ack: bool = False):
    ver_repo = MagicMock()
    ver_repo.get_by_vid = AsyncMock(return_value=ver or _ver())

    task_repo = MagicMock()
    task_repo.list_for_verification = AsyncMock(return_value=tasks or [])

    view_repo = MagicMock()
    view_repo.get_for_customer = AsyncMock(return_value=MagicMock() if has_ack else None)
    view_repo.create_return_model = AsyncMock(return_value=MagicMock())

    version_repo = MagicMock()
    version_repo.current_for_vid = AsyncMock(return_value=MagicMock(version_string="v1.0"))

    svc = ReportAssemblyService(
        verification_repo=ver_repo,
        task_repo=task_repo,
        view_repo=view_repo,
        version_repo=version_repo,
    )
    return svc, ver_repo, view_repo


class TestAssemble:
    async def test_basic_includes_only_registry(self):
        tasks = [
            _task(TaskRole.REGISTRY.value, {"title_doc_assessment": "AUTHENTIC"}),
        ]
        svc, _, _ = _make_service(tasks=tasks)
        report = await svc.assemble("VID-001", customer_id="cust-1")
        assert report.registry_findings is not None
        assert report.physical_findings is None
        assert report.boundary_findings is None
        assert report.legal_opinion is None

    async def test_standard_includes_physical_and_boundary(self):
        tasks = [
            _task(TaskRole.REGISTRY.value, {}),
            _task(TaskRole.FIELD.value, {"occupancy_status": "OCCUPIED"}),
            _task(TaskRole.SURVEYOR.value, {"boundary_coords": {"lat": 6.5, "lng": 3.4}}),
        ]
        svc, _, _ = _make_service(ver=_ver(tier="STANDARD"), tasks=tasks)
        report = await svc.assemble("VID-001", customer_id="cust-1")
        assert report.physical_findings is not None
        assert report.boundary_findings is not None
        assert report.legal_opinion is None

    async def test_premium_includes_legal_opinion(self):
        tasks = [
            _task(TaskRole.REGISTRY.value, {}),
            _task(TaskRole.FIELD.value, {}),
            _task(TaskRole.SURVEYOR.value, {}),
            _task(TaskRole.LAWYER.value, {"document_authenticity": "AUTHENTIC"}),
        ]
        svc, _, _ = _make_service(ver=_ver(tier="PREMIUM"), tasks=tasks)
        report = await svc.assemble("VID-001", customer_id="cust-1")
        assert report.legal_opinion is not None

    async def test_raises_if_not_completed(self):
        svc, _, _ = _make_service(ver=_ver(status=VerificationStatus.UNDER_REVIEW.value))
        with pytest.raises(ValidationException, match="completed"):
            await svc.assemble("VID-001", customer_id="cust-1")

    async def test_raises_if_not_found(self):
        svc, ver_repo, _ = _make_service()
        ver_repo.get_by_vid = AsyncMock(return_value=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.assemble("VID-MISSING", customer_id="cust-1")

    async def test_ownership_check(self):
        svc, _, _ = _make_service(ver=_ver(customer_id="cust-1"))
        with pytest.raises(ForbiddenException):
            await svc.assemble("VID-001", customer_id="cust-OTHER")


class TestAcknowledgement:
    async def test_record_acknowledgement_is_idempotent(self):
        svc, _, view_repo = _make_service(has_ack=True)
        await svc.record_acknowledgement("VID-001", "cust-1", ip_address="1.2.3.4")
        view_repo.create_return_model.assert_not_called()

    async def test_first_acknowledgement_creates_record(self):
        svc, _, view_repo = _make_service(has_ack=False)
        await svc.record_acknowledgement("VID-001", "cust-1", ip_address="1.2.3.4")
        view_repo.create_return_model.assert_called_once()

    async def test_has_acknowledged_false_initially(self):
        svc, _, view_repo = _make_service(has_ack=False)
        result = await svc.has_acknowledged("VID-001", "cust-1")
        assert result is False

    async def test_has_acknowledged_true_after_acknowledge(self):
        svc, _, view_repo = _make_service(has_ack=True)
        result = await svc.has_acknowledged("VID-001", "cust-1")
        assert result is True
