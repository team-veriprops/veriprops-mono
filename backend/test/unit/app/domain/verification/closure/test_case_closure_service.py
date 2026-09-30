"""CaseClosureService (§6.4): closing a paid case, its hold, and how it ends.

A close that owes money never sends it: the case goes on hold and a request waits for Finance.
While on hold its agents are stopped. Finance approving finishes the close (delivered work paid,
the rest cancelled); rejecting lifts the hold. A close that owes nothing ends at once.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus, VerificationTier
from main.app.domain.payment.refund_request.models import RefundSource
from main.app.domain.verification.closure.models import CloseCaseDto, CloseReason
from main.app.domain.verification.closure.service import CaseClosureService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from test.utils.repo_fakes import fake_claim_transition

PAID = 15_000_000


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


@pytest.fixture
def events(monkeypatch):
    import main.app.domain.verification.closure.service as module
    published = []
    monkeypatch.setattr(module, "publish_domain_event", AsyncMock(side_effect=lambda e: published.append(e)))
    return published


def _case(status=VerificationStatus.IN_PROGRESS, closure_reason=None):
    return SimpleNamespace(
        id="ver-1", vid="VP-1", customer_id="cust-1", status=status.value, closure_reason=closure_reason,
        tier=VerificationTier.STANDARD.value, currency="NGN", deleted=False,
    )


def _task(tid, role, state, agent="agent-1"):
    return SimpleNamespace(id=tid, role=role.value, state=state.value, assigned_agent_id=agent,
                           in_pool=False, deleted=False, verification_id="ver-1")


def _service(case, tasks, refundable=PAID, surcharge=20):
    svc = object.__new__(CaseClosureService)
    svc._verifications = MagicMock()
    svc._verifications.get_model = AsyncMock(return_value=case)
    svc._verifications.claim_transition = fake_claim_transition(lambda _id: case)
    rows = {t.id: t for t in tasks}
    svc._tasks = MagicMock()
    svc._tasks.list_for_verification = AsyncMock(return_value=tasks)
    svc._tasks.claim_transition = fake_claim_transition(rows)
    svc._reviews = MagicMock()
    svc._reviews.accrue_commissions = AsyncMock()
    svc._payments = MagicMock()
    svc._payments.refundable_minor = AsyncMock(return_value=refundable)
    svc._refund_requests = MagicMock()
    svc._refund_requests.file = AsyncMock(return_value=SimpleNamespace(id="req-1"))
    svc._config = MagicMock()
    svc._config.get_int = AsyncMock(return_value=surcharge)
    svc._audit = MagicMock()
    return svc


def _tasks():
    return [
        _task("t-field", AgentRole.FIELD, TaskState.SUBMITTED, agent="agent-field"),
        _task("t-registry", AgentRole.REGISTRY, TaskState.IN_PROGRESS, agent="agent-registry"),
        _task("t-surveyor", AgentRole.SURVEYOR, TaskState.PENDING, agent=None),
    ]


class TestQuote:
    async def test_the_quote_states_the_refund_the_ending_and_each_agents_outcome(self):
        svc = _service(_case(VerificationStatus.PAID), _tasks())

        quote = await svc.quote("ver-1", CloseReason.CUSTOMER_WITHDREW)

        assert (quote.refund_minor, quote.resulting_status, quote.requires_approval) == (
            12_000_000, VerificationStatus.CANCELLED, True,
        )
        assert {(a.task_id, a.paid) for a in quote.agents} == {
            ("t-field", True), ("t-registry", False), ("t-surveyor", False),
        }

    @pytest.mark.parametrize("status", [VerificationStatus.SUBMITTED, VerificationStatus.COMPLETED])
    async def test_only_a_paid_unfinished_case_can_be_closed(self, status):
        with pytest.raises(InvalidResourceStateException):
            await _service(_case(status), []).quote("ver-1", CloseReason.DUPLICATE)

    async def test_a_case_already_closing_cannot_be_closed_again(self):
        with pytest.raises(InvalidResourceStateException):
            await _service(_case(closure_reason=CloseReason.DUPLICATE.value), []).quote("ver-1", CloseReason.DUPLICATE)


class TestClose:
    async def test_a_close_that_owes_money_holds_the_case_and_files_it_for_finance(self, events):
        case, tasks = _case(), _tasks()
        svc = _service(case, tasks)

        result = await svc.close("ver-1", CloseCaseDto(reason=CloseReason.DUPLICATE, note="Paid twice by mistake"), "ops-1")

        assert (result.on_hold, result.refund_minor, result.refund_request_id) == (True, PAID, "req-1")
        assert case.status == VerificationStatus.IN_PROGRESS.value
        assert case.closure_reason == CloseReason.DUPLICATE.value
        filed = svc._refund_requests.file.await_args.kwargs
        assert (filed["source"], filed["amount_minor"], filed["requested_by"]) == (RefundSource.CASE_CLOSURE, PAID, "ops-1")
        # Nothing is paid or cancelled yet: Finance has not decided.
        svc._reviews.accrue_commissions.assert_not_awaited()
        assert tasks[1].state == TaskState.IN_PROGRESS.value
        told = {e.type: e.recipient_user_ids for e in events}
        # Only an agent with work in hand is told to stop; the delivered one has nothing to stop.
        assert told[EventType.TASK_ON_HOLD] == ("agent-registry",)
        assert told[EventType.CASE_ON_HOLD] == ("cust-1",)

    async def test_a_close_that_owes_nothing_ends_the_case_at_once(self, events):
        case, tasks = _case(), _tasks()
        svc = _service(case, tasks)

        result = await svc.close("ver-1", CloseCaseDto(reason=CloseReason.FRAUD, note="Forged title documents"), "ops-1")

        assert (result.on_hold, result.status) == (False, VerificationStatus.CANCELLED)
        assert case.status == VerificationStatus.CANCELLED.value
        svc._refund_requests.file.assert_not_awaited()

    async def test_two_closes_at_once_hold_the_case_once(self):
        case = _case()
        svc = _service(case, _tasks())
        svc._verifications.claim_transition = AsyncMock(return_value=None)  # the other close won

        with pytest.raises(InvalidResourceStateException):
            await svc.close("ver-1", CloseCaseDto(reason=CloseReason.DUPLICATE, note="Paid twice by mistake"), "ops-1")
        svc._refund_requests.file.assert_not_awaited()


class TestFinalize:
    async def test_delivered_work_is_paid_and_the_rest_cancelled(self, events):
        case, tasks = _case(closure_reason=CloseReason.CANNOT_DELIVER.value), _tasks()
        svc = _service(case, tasks)

        status = await svc.finalize("ver-1", "finance-1", "No coverage in the area")

        assert status == VerificationStatus.FAILED
        assert case.status == VerificationStatus.FAILED.value
        paid = svc._reviews.accrue_commissions.await_args.args[1]
        assert [t.id for t in paid] == ["t-field"]
        assert [t.state for t in tasks] == [
            TaskState.SUBMITTED.value, TaskState.CANCELLED.value, TaskState.CANCELLED.value,
        ]
        told = {e.type: set(e.recipient_user_ids) for e in events}
        assert told[EventType.TASK_CASE_CLOSED] == {"agent-field", "agent-registry"}
        # The audit trail keeps what each task was, not what the claim made it.
        cancelled = [c.kwargs for c in svc._audit.schedule.call_args_list if c.kwargs.get("to_state") == TaskState.CANCELLED.value]
        assert {(a["resource_id"], a["from_state"]) for a in cancelled} == {
            ("t-registry", TaskState.IN_PROGRESS.value), ("t-surveyor", TaskState.PENDING.value),
        }
        assert told[EventType.CASE_CLOSED] == {"cust-1"}

    async def test_a_close_loses_to_a_concurrent_release_and_pays_or_cancels_nothing(self):
        """Released between the hold and Finance's approval: the claim fails, so no task is
        touched — and Finance's approval, which refunds after this, stops here too."""
        case = _case(closure_reason=CloseReason.DUPLICATE.value)
        tasks = _tasks()
        svc = _service(case, tasks)
        case.status = VerificationStatus.COMPLETED.value

        with pytest.raises(InvalidResourceStateException):
            await svc.finalize("ver-1", "finance-1", None)
        svc._reviews.accrue_commissions.assert_not_awaited()
        assert tasks[1].state == TaskState.IN_PROGRESS.value

    async def test_a_case_not_being_closed_cannot_be_finalized(self):
        with pytest.raises(InvalidResourceStateException):
            await _service(_case(), _tasks()).finalize("ver-1", "finance-1", None)


class TestLiftHold:
    async def test_a_rejected_refund_puts_the_case_back_to_work(self, events):
        case, tasks = _case(closure_reason=CloseReason.CUSTOMER_WITHDREW.value), _tasks()
        svc = _service(case, tasks)

        await svc.lift_hold("ver-1", "finance-1", "The customer changed their mind")

        assert case.closure_reason is None
        assert case.status == VerificationStatus.IN_PROGRESS.value
        lifted = svc._audit.schedule.call_args.kwargs
        assert lifted["details"]["reason"] == CloseReason.CUSTOMER_WITHDREW.value
        told = {e.type: e.recipient_user_ids for e in events}
        assert told[EventType.TASK_RESUMED] == ("agent-registry",)
        assert told[EventType.CASE_RESUMED] == ("cust-1",)
