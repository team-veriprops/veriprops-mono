"""DisputeService (§14.3): open within the window (freeze + DISPUTED), agent defence, and the
three admin resolutions with correct transitions + commission handling."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, ReportRevisionKind, VerificationStatus, VerificationTier
from main.app.domain.verification.dispute.models import (
    DisputeOutcome,
    DisputeStatus,
    DisputeType,
    OpenDisputeDto,
    ResolveDisputeDto,
)
from main.app.domain.verification.dispute.service import DisputeService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidResourceStateException,
    ValidationException,
)

_LONG = "x" * 120  # ≥ 100-char description


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


def _verification(status=VerificationStatus.COMPLETED):
    return SimpleNamespace(id="v-1", vid="VP-1", tier=VerificationTier.STANDARD.value,
                           status=status.value, customer_id="cust-1")


def _report(days_ago=1):
    return SimpleNamespace(id="rep-1", released_at=Utils.datetime_now() - timedelta(days=days_ago))


def _dispute(status=DisputeStatus.OPEN, agent_id="agent-1"):
    return SimpleNamespace(
        id="d-1", verification_id="v-1", customer_id="cust-1",
        dispute_type=DisputeType.INACCURATE_FINDING.value, description=_LONG, evidence=None,
        status=status.value, target_role=AgentRole.SURVEYOR.value, agent_id=agent_id,
        agent_defence_text=None, agent_defence_at=None, resolution_outcome=None,
        resolution_note=None, date_created=Utils.datetime_now(),
    )


def _service(verification=None, report=None, dispute=None, window_days=30):
    svc = object.__new__(DisputeService)
    svc._dispute_repo = MagicMock()
    svc._verifications = MagicMock()
    svc._verification_repo = MagicMock()
    svc._dispute_reports = MagicMock()
    svc._reviews = MagicMock()
    svc._commissions = MagicMock()
    svc._payments = MagicMock()
    svc._config = MagicMock()
    svc._tasks = MagicMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()

    v = verification if verification is not None else _verification()
    svc._verifications.get_owned = AsyncMock(return_value=v)
    svc._verification_repo.get_model = AsyncMock(return_value=v)
    svc._verification_repo.update = AsyncMock()
    svc._dispute_reports.get_released = AsyncMock(return_value=report if report is not None else _report())
    svc._config.get_int = AsyncMock(return_value=window_days)
    svc._tasks.get_by_role = AsyncMock(return_value=SimpleNamespace(assigned_agent_id="agent-1"))
    svc._dispute_repo.create_return_model = AsyncMock(return_value=_dispute())
    svc._dispute_repo.get_model = AsyncMock(return_value=dispute or _dispute())
    svc._dispute_repo.get_open_for_agent = AsyncMock(return_value=dispute)
    svc._dispute_repo.update = AsyncMock()
    svc._commissions.freeze_for_verification = AsyncMock()
    svc._commissions.unfreeze_for_verification = AsyncMock()
    svc._commissions.reverse_for_verification = AsyncMock()
    svc._payments.refund = AsyncMock(return_value=12_000_000)
    svc._reviews.reopen_task = AsyncMock()
    return svc


def _open_dto():
    return OpenDisputeDto(dispute_type=DisputeType.INACCURATE_FINDING, description=_LONG,
                          target_role=AgentRole.SURVEYOR)


class TestOpen:
    async def test_open_transitions_and_freezes(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service()
        await svc.open("v-1", "cust-1", _open_dto())
        upd = svc._verification_repo.update.await_args.args[1]
        assert upd.status == VerificationStatus.DISPUTED.value
        svc._commissions.freeze_for_verification.assert_awaited_once()

    async def test_open_requires_100_chars(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.open("v-1", "cust-1", OpenDisputeDto(
                dispute_type=DisputeType.OTHER, description="too short"))

    async def test_open_blocked_outside_window(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(report=_report(days_ago=40), window_days=30)
        with pytest.raises(ValidationException):
            await svc.open("v-1", "cust-1", _open_dto())

    async def test_open_blocked_when_not_completed(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(verification=_verification(status=VerificationStatus.IN_PROGRESS))
        with pytest.raises(InvalidResourceStateException):
            await svc.open("v-1", "cust-1", _open_dto())


class TestAgentDefence:
    async def test_defence_records_text(self):
        svc = _service(dispute=_dispute())
        await svc.agent_defend("d-1", "agent-1", "I surveyed the correct plot on 3 Jan.")
        dto = svc._dispute_repo.update.await_args.args[1]
        assert "surveyed" in dto.agent_defence_text

    async def test_defence_forbidden_for_other_agent(self):
        svc = _service(dispute=None)  # get_open_for_agent returns None
        with pytest.raises(ForbiddenException):
            await svc.agent_defend("d-1", "agent-2", "not mine")


class TestResolve:
    async def _resolve(self, monkeypatch, outcome, **kwargs):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        v = _verification(status=VerificationStatus.DISPUTED)
        svc = _service(verification=v, dispute=_dispute(status=DisputeStatus.OPEN))
        await svc.resolve("d-1", ResolveDisputeDto(outcome=outcome, note="admin decision", **kwargs), "admin-1")
        return svc

    async def test_reject_back_to_completed(self, monkeypatch):
        svc = await self._resolve(monkeypatch, DisputeOutcome.REJECTED)
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.COMPLETED.value in statuses
        svc._commissions.unfreeze_for_verification.assert_awaited_once()

    async def test_full_refund_refunds_and_reverses(self, monkeypatch):
        svc = await self._resolve(monkeypatch, DisputeOutcome.FULL_REFUND)
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.REFUNDED.value in statuses
        svc._payments.refund.assert_awaited_once()
        svc._commissions.reverse_for_verification.assert_awaited_once()

    async def test_partial_recheck_reopens_and_marks_v2(self, monkeypatch):
        svc = await self._resolve(
            monkeypatch, DisputeOutcome.PARTIAL_RECHECK, scope_roles=[AgentRole.SURVEYOR]
        )
        upd = [c.args[1] for c in svc._verification_repo.update.call_args_list]
        assert any(u.status == VerificationStatus.IN_PROGRESS.value for u in upd)
        assert any(u.pending_revision_kind == ReportRevisionKind.RECHECK.value for u in upd)
        svc._reviews.reopen_task.assert_awaited_once()

    async def test_resolve_requires_note(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        v = _verification(status=VerificationStatus.DISPUTED)
        svc = _service(verification=v, dispute=_dispute(status=DisputeStatus.OPEN))
        with pytest.raises(ValidationException):
            await svc.resolve("d-1", ResolveDisputeDto(outcome=DisputeOutcome.REJECTED, note="  "), "admin-1")
