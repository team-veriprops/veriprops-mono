"""Unit tests for audit_ctx queue / drain / reset lifecycle and AuditLogService.schedule().

No database or DI container is used. AuditLogService is constructed by hand so
@inject and @transactional decorators do not interfere.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.appodus_utils.decorators.audit_ctx import (
    drain_audit_writes,
    reset_audit_ctx,
    schedule_audit_write,
)


@pytest.fixture(autouse=True)
def clean_ctx():
    reset_audit_ctx()
    yield
    reset_audit_ctx()


@pytest.fixture
def mock_repo():
    r = MagicMock()
    r.create = AsyncMock()
    return r


def _make_svc(mock_repo) -> AuditLogService:
    """Build AuditLogService bypassing @inject for isolated unit testing."""
    svc = object.__new__(AuditLogService)
    svc._repo = mock_repo
    return svc


# ── audit_ctx primitives ──────────────────────────────────────────────────────

async def test_drain_executes_enqueued_factory():
    called = []

    async def factory():
        called.append(1)

    schedule_audit_write(factory)
    assert called == []
    await drain_audit_writes()
    assert called == [1]


async def test_drain_empty_queue_is_a_noop():
    await drain_audit_writes()  # must not raise


async def test_drain_is_idempotent():
    called = []

    async def factory():
        called.append(1)

    schedule_audit_write(factory)
    await drain_audit_writes()
    await drain_audit_writes()
    assert len(called) == 1


async def test_reset_clears_pending_queue():
    called = []

    async def factory():
        called.append(1)

    schedule_audit_write(factory)
    reset_audit_ctx()
    await drain_audit_writes()
    assert called == []


async def test_multiple_factories_drain_in_insertion_order():
    order = []
    for i in range(3):
        n = i

        async def factory(n=n):
            order.append(n)

        schedule_audit_write(factory)
    await drain_audit_writes()
    assert order == [0, 1, 2]


# ── AuditLogService.schedule() ────────────────────────────────────────────────

async def test_schedule_does_not_call_repo_immediately(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(AuditActionType.VERIFICATION_SUBMITTED, "Verification", "vid-1", actor_id="uid-1")
    mock_repo.create.assert_not_called()


async def test_schedule_then_drain_calls_repo_once(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(
        AuditActionType.VERIFICATION_SUBMITTED,
        "Verification",
        "vid-1",
        actor_id="uid-1",
    )
    await drain_audit_writes()
    mock_repo.create.assert_called_once()
    dto = mock_repo.create.call_args[0][0]
    assert dto.action == AuditActionType.VERIFICATION_SUBMITTED
    assert dto.resource_type == "Verification"
    assert dto.resource_id == "vid-1"
    assert dto.actor_id == "uid-1"


async def test_schedule_captures_all_optional_fields(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(
        AuditActionType.AGENT_APPLICATION_REJECTED,
        resource_type="AgentApplication",
        resource_id="app-123",
        actor_id="admin-456",
        from_state="PENDING",
        to_state="REJECTED",
        meta={"reason": "incomplete documents"},
        ip_address="1.2.3.4",
    )
    await drain_audit_writes()
    dto = mock_repo.create.call_args[0][0]
    assert dto.action == AuditActionType.AGENT_APPLICATION_REJECTED
    assert dto.resource_type == "AgentApplication"
    assert dto.resource_id == "app-123"
    assert dto.actor_id == "admin-456"
    assert dto.from_state == "PENDING"
    assert dto.to_state == "REJECTED"
    assert dto.meta == {"reason": "incomplete documents"}
    assert dto.ip_address == "1.2.3.4"
    assert dto.occurred_at is not None


async def test_two_schedules_produce_two_writes(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(AuditActionType.VERIFICATION_SUBMITTED, "Verification", "v1")
    svc.schedule(AuditActionType.VERIFICATION_STATE_CHANGED, "Verification", "v1")
    await drain_audit_writes()
    assert mock_repo.create.call_count == 2


async def test_reset_between_schedule_and_drain_produces_no_write(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(AuditActionType.VERIFICATION_SUBMITTED, "Verification", "v1")
    reset_audit_ctx()
    await drain_audit_writes()
    mock_repo.create.assert_not_called()


async def test_second_drain_after_clear_is_a_noop(mock_repo):
    svc = _make_svc(mock_repo)
    svc.schedule(AuditActionType.PAYMENT_INITIATED, "Payment", "pay-1")
    await drain_audit_writes()
    assert mock_repo.create.call_count == 1
    await drain_audit_writes()
    assert mock_repo.create.call_count == 1  # not called again
