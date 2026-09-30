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
from test.utils.repo_fakes import fake_claim_transition
from main.app.domain.payment.models import RefundOutcome
from main.app.domain.payment.refund_request.models import RefundSource

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
                           status=status.value, customer_id="cust-1", currency="NGN")


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
    held = dispute or _dispute()
    svc._dispute_repo.get_model = AsyncMock(return_value=held)
    # Status moves are claims on the rows this service reads.
    svc._verification_repo.claim_transition = fake_claim_transition(lambda _id: v)
    svc._dispute_repo.claim_transition = fake_claim_transition(lambda _id: held)
    svc._dispute_repo.get_open_for_agent = AsyncMock(return_value=dispute)
    svc._dispute_repo.update = AsyncMock()
    svc._commissions.freeze_for_verification = AsyncMock()
    svc._commissions.unfreeze_for_verification = AsyncMock()
    svc._commissions.reverse_for_verification = AsyncMock()
    svc._payments.refund = AsyncMock(return_value=RefundOutcome(refunded_minor=12_000_000))
    svc._payments.refundable_minor = AsyncMock(return_value=12_000_000)
    svc._refund_requests = MagicMock()
    svc._refund_requests.file = AsyncMock()
    svc._reviews.reopen_task = AsyncMock()
    return svc


def _open_dto():
    return OpenDisputeDto(dispute_type=DisputeType.INACCURATE_FINDING, description=_LONG,
                          target_role=AgentRole.SURVEYOR)


class TestOpen:
    async def test_open_transitions_and_freezes(self, monkeypatch):
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        v = _verification()
        svc = _service(verification=v)
        await svc.open("v-1", "cust-1", _open_dto())
        assert v.status == VerificationStatus.DISPUTED.value
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
    async def _resolve(self, monkeypatch, outcome, track=None, **kwargs):
        """*track*, when given, collects the order of the resolution's side effects."""
        import main.app.domain.verification.dispute.service as mod
        seen = track if track is not None else []
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock(side_effect=lambda *_: seen.append("event")))
        v = _verification(status=VerificationStatus.DISPUTED)
        dispute = _dispute(status=DisputeStatus.OPEN)
        svc = _service(verification=v, dispute=dispute)
        svc._payments.refund = AsyncMock(side_effect=lambda *a, **k: seen.append("refund") or RefundOutcome())
        svc._commissions.reverse_for_verification = AsyncMock(side_effect=lambda *a, **k: seen.append("reverse"))
        svc._audit.schedule = MagicMock(side_effect=lambda **k: seen.append("audit"))
        await svc.resolve("d-1", ResolveDisputeDto(outcome=outcome, note="admin decision", **kwargs), "admin-1")
        # The resolution itself is the claim, recorded with its outcome and who decided.
        assert dispute.status == DisputeStatus.RESOLVED.value
        assert (dispute.resolution_outcome, dispute.resolved_by) == (outcome.value, "admin-1")
        return svc

    async def test_reject_back_to_completed(self, monkeypatch):
        svc = await self._resolve(monkeypatch, DisputeOutcome.REJECTED)
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.COMPLETED.value in statuses
        svc._commissions.unfreeze_for_verification.assert_awaited_once()

    async def test_an_upheld_dispute_files_the_full_refund_for_finance_and_waits(self, monkeypatch):
        """No customer money leaves unapproved (§8.5): the refund waits in Finance's queue, and
        the case stays DISPUTED with commissions frozen until Finance approves it."""
        svc = await self._resolve(monkeypatch, DisputeOutcome.FULL_REFUND)
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.REFUNDED.value not in statuses
        svc._payments.refund.assert_not_awaited()
        svc._commissions.reverse_for_verification.assert_not_awaited()
        filed = svc._refund_requests.file.await_args.kwargs
        assert (filed["source"], filed["amount_minor"], filed["requested_by"]) == (
            RefundSource.DISPUTE_UPHELD, 12_000_000, "admin-1",
        )

    async def test_nothing_is_filed_when_nothing_is_refundable(self, monkeypatch):
        """Every charge already refunded, or held under a chargeback."""
        import main.app.domain.verification.dispute.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(verification=_verification(status=VerificationStatus.DISPUTED), dispute=_dispute())
        svc._payments.refundable_minor = AsyncMock(return_value=0)
        await svc.resolve("d-1", ResolveDisputeDto(outcome=DisputeOutcome.FULL_REFUND, note="admin decision"), "admin-1")
        svc._refund_requests.file.assert_not_awaited()
        # Nothing waits on Finance, so the case settles now.
        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.REFUNDED.value in statuses
        svc._commissions.reverse_for_verification.assert_awaited_once()

    async def test_finance_approving_settles_the_case_as_refunded(self):
        v = _verification(status=VerificationStatus.DISPUTED)
        svc = _service(verification=v, dispute=_dispute())

        await svc.settle_full_refund("v-1", "finance-1")

        statuses = [c.args[1].status for c in svc._verification_repo.update.call_args_list if c.args[1].status]
        assert VerificationStatus.REFUNDED.value in statuses
        svc._commissions.reverse_for_verification.assert_awaited_once_with("v-1", "finance-1")

    async def test_finance_refusing_reopens_the_dispute_for_ops(self):
        upheld = _dispute(status=DisputeStatus.RESOLVED)
        upheld.resolution_outcome = DisputeOutcome.FULL_REFUND.value
        svc = _service(verification=_verification(status=VerificationStatus.DISPUTED), dispute=upheld)
        svc._dispute_repo.list_for_verification = AsyncMock(return_value=[upheld])

        await svc.reopen_refused_refund("v-1", "finance-1", "Evidence does not support a refund")

        assert (upheld.status, upheld.resolution_outcome) == (DisputeStatus.OPEN.value, None)
        svc._commissions.reverse_for_verification.assert_not_awaited()

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
