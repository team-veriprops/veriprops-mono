"""Money and workflow transitions happen once, whichever concurrent request gets there first.

Each test plays the *losing* request: it read the row while the move was still open (a
stale snapshot), and by the time it writes, another request has already made the move. The
write is a claim — a conditional UPDATE — so the loser gets a domain error (or quietly
stands down, for a webhook or sweep) and never repeats the effects that follow the move:
money, commissions, reports, notifications.

Where the check is over many rows (a balance, an agent's capacity, a user's devices), the
writers are serialised with a transaction-scoped advisory lock, taken before the read.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import TaskState, VerificationStatus
from main.app.domain.payment.models import PaymentStatus
from main.app.domain.payout.models import PayoutDecisionDto, PayoutStatus, RequestPayoutDto
from main.app.domain.referral.credit.models import ReferralCreditStatus
from main.app.domain.user.admin_invitation.models import AdminInvitationStatus
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.verification.dispute.models import DisputeOutcome, DisputeStatus, ResolveDisputeDto
from main.app.domain.verification.recheck.models import DecideRecheckDto, RecheckStatus
from main.app.domain.verification.upgrade.models import UpgradeStatus
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    InvalidTokenException,
)
from test.utils.repo_fakes import fake_claim_transition


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture
def events(monkeypatch):
    """Every domain event any of the services under test publishes."""
    published = []

    async def _publish(event):
        published.append(event)

    from main.app.domain.payout import service as payout_module
    from main.app.domain.referral import service as referral_module
    from main.app.domain.verification import service as verification_module
    from main.app.domain.verification.dispute import service as dispute_module
    from main.app.domain.verification.upgrade import service as upgrade_module
    for module in (payout_module, referral_module, verification_module, dispute_module, upgrade_module):
        monkeypatch.setattr(module, "publish_domain_event", _publish)
    return published


def _locks(monkeypatch, module, order=None):
    """Record the advisory locks *module* takes (and, optionally, when)."""
    taken = []

    async def _lock(name):
        taken.append(name)
        if order is not None:
            order.append(f"lock:{name}")

    monkeypatch.setattr(module, "advisory_xact_lock", _lock)
    return taken


def _snapshot(row, **stale):
    """What a request read before the other one committed its move."""
    return SimpleNamespace(**{**vars(row), **stale})


# ── Money ─────────────────────────────────────────────────────────


def _payout(status=PayoutStatus.REQUESTED):
    return SimpleNamespace(
        id="p-1", agent_id="a-1", amount_minor=50_000, status=status.value, adjustment_minor=0,
        note=None, decided_at=None, decided_by=None, deleted=False,
    )


def _payout_service(db_row, read=None):
    from main.app.domain.payout.service import PayoutService

    svc = object.__new__(PayoutService)
    svc._payout_repo = AsyncMock()
    svc._payout_repo.get_model = AsyncMock(return_value=read or db_row)
    svc._payout_repo.claim_transition = fake_claim_transition({"p-1": db_row})
    svc._earnings = AsyncMock()
    svc._banks = AsyncMock()
    svc._audit = MagicMock()
    svc._config = AsyncMock()
    svc._config.get_int = AsyncMock(return_value=2)
    return svc


class TestPayouts:
    async def test_request_serialises_on_the_agent_before_reading_the_balance(self, monkeypatch):
        from main.app.domain.payout import service as payout_module

        order = []
        locks = _locks(monkeypatch, payout_module, order)
        svc = _payout_service(_payout())

        async def _available(agent_id):
            order.append("balance")
            return 100_000

        svc._earnings.available_minor = AsyncMock(side_effect=_available)
        svc._payout_repo.create_return_model = AsyncMock(return_value=_payout())

        await svc.request("a-1", RequestPayoutDto(
            amount_minor=60_000, bank_name="GT", account_number="1", account_name="A",
        ))

        # A second request waits here until the first commits, then sees its reservation
        # in the balance — two withdrawals can no longer both spend the same money.
        assert locks == ["payout:a-1"]
        assert order == ["lock:payout:a-1", "balance"]

    async def test_a_second_approval_is_refused_and_pays_nothing(self, events):
        db = _payout(PayoutStatus.PAID)  # another finance admin approved first
        svc = _payout_service(db, read=_snapshot(db, status=PayoutStatus.REQUESTED.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.approve("p-1", "fin-2", PayoutDecisionDto())

        assert events == []
        svc._audit.schedule.assert_not_called()

    async def test_cancel_loses_to_a_concurrent_approval(self):
        db = _payout(PayoutStatus.PAID)
        svc = _payout_service(db, read=_snapshot(db, status=PayoutStatus.REQUESTED.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("a-1", "p-1")
        assert db.status == PayoutStatus.PAID.value

    async def test_an_adjustment_cannot_land_on_a_decided_payout(self):
        db = _payout(PayoutStatus.REJECTED)
        svc = _payout_service(db, read=_snapshot(db, status=PayoutStatus.HELD.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.adjust("p-1", "fin-1", PayoutDecisionDto(adjustment_minor=-100))
        assert db.adjustment_minor == 0

    async def test_approval_records_the_decision_in_the_claim(self, events):
        db = _payout(PayoutStatus.HELD)
        svc = _payout_service(db)

        await svc.approve("p-1", "fin-1", PayoutDecisionDto(note="ok"))

        assert db.status == PayoutStatus.PAID.value
        assert (db.decided_by, db.note) == ("fin-1", "ok")
        assert db.decided_at is not None
        assert len(events) == 1


def _payment(status=PaymentStatus.INITIATED, purpose="VERIFICATION"):
    return SimpleNamespace(
        id="pay-1", tx_ref="tx-1", verification_id="v-1", customer_id="c-1", amount_minor=10_000,
        status=status.value, purpose=purpose, failure_count=0, deleted=False,
        gateway_event_id=None, refunded_amount_minor=None, card_fingerprint=None,
    )


def _payment_service(db_row, read=None):
    from main.app.domain.payment.service import PaymentService

    svc = object.__new__(PaymentService)
    svc._payment_repo = AsyncMock()
    svc._payment_repo.get_by_tx_ref = AsyncMock(return_value=read or db_row)
    svc._payment_repo.list_for_verification = AsyncMock(return_value=[read or db_row])
    svc._payment_repo.claim_transition = fake_claim_transition({"pay-1": db_row})
    svc._idempotency = AsyncMock()
    svc._idempotency.claim = AsyncMock(return_value=True)
    svc._verification_service = AsyncMock()
    svc._task_service = AsyncMock()
    svc._user_service = AsyncMock()
    svc._audit = MagicMock()
    svc._award_referral_credit = AsyncMock()
    return svc


def _webhook(succeeded=True, event_id="evt-2"):
    from main.app.domain.payment.models import PaymentWebhookDto

    return PaymentWebhookDto(event_id=event_id, tx_ref="tx-1", succeeded=succeeded)


class TestPaymentWebhook:
    async def test_a_second_success_event_for_the_same_charge_settles_nothing(self):
        db = _payment(PaymentStatus.SUCCEEDED)
        svc = _payment_service(db, read=_snapshot(db, status=PaymentStatus.INITIATED.value))

        assert await svc.handle_webhook(_webhook(succeeded=True)) is False

        svc._verification_service.mark_paid.assert_not_called()
        svc._task_service.prepare_for_paid.assert_not_called()
        svc._award_referral_credit.assert_not_called()

    async def test_a_late_failure_never_downgrades_a_settled_payment(self):
        db = _payment(PaymentStatus.SUCCEEDED)
        svc = _payment_service(db, read=_snapshot(db, status=PaymentStatus.INITIATED.value))

        assert await svc.handle_webhook(_webhook(succeeded=False)) is False
        assert db.status == PaymentStatus.SUCCEEDED.value

    async def test_failures_are_counted_in_sql(self):
        db = _payment(PaymentStatus.FAILED)
        db.failure_count = 1
        svc = _payment_service(db)

        await svc.handle_webhook(_webhook(succeeded=False))

        assert db.failure_count == 2
        assert svc._payment_repo.claim_transition.call_args.kwargs["increments"] == {"failure_count": 1}

    async def test_a_concurrent_refund_refunds_once(self):
        db = _payment(PaymentStatus.REFUNDED)
        svc = _payment_service(db, read=_snapshot(db, status=PaymentStatus.SUCCEEDED.value))

        assert await svc.refund("v-1", "admin-1") == 0
        svc._audit.schedule.assert_not_called()


def _verification(status, **extra):
    base = dict(
        id="v-1", vid="VP-1", customer_id="c-1", status=status.value, tier="STANDARD",
        referral_credit_applied_minor=0, deleted=False,
    )
    return SimpleNamespace(**{**base, **extra})


class TestMarkPaid:
    def _service(self, db_row, read):
        from main.app.domain.verification.service import VerificationService

        svc = object.__new__(VerificationService)
        svc._verification_repo = AsyncMock()
        reads = iter([read, db_row, db_row])
        svc._verification_repo.get_model = AsyncMock(side_effect=lambda _id: next(reads))
        svc._verification_repo.claim_transition = fake_claim_transition({"v-1": db_row})
        svc._users = AsyncMock()
        svc._set_paid_timestamps = AsyncMock()
        return svc

    async def test_a_concurrent_confirmation_debits_and_notifies_once(self, events):
        db = _verification(VerificationStatus.PAID, referral_credit_applied_minor=500)
        svc = self._service(db, read=_snapshot(db, status=VerificationStatus.PAYMENT_PENDING.value))

        out = await svc.mark_paid("v-1")

        assert out.status == VerificationStatus.PAID.value
        svc._users.spend_credit_balance.assert_not_called()
        assert events == []

    async def test_the_winner_spends_the_applied_credit_in_sql(self, events):
        db = _verification(VerificationStatus.PAYMENT_PENDING, referral_credit_applied_minor=500)
        svc = self._service(db, read=_snapshot(db))

        await svc.mark_paid("v-1")

        assert db.status == VerificationStatus.PAID.value
        svc._users.spend_credit_balance.assert_awaited_once_with("c-1", 500)
        assert len(events) == 1


class TestReferralCreditSweep:
    async def test_a_credit_cleared_by_an_overlapping_sweep_is_not_paid_twice(self, events):
        from main.app.domain.referral.service import ReferralService

        db = SimpleNamespace(
            id="rc-1", referrer_user_id="r-1", amount_minor=5_000,
            status=ReferralCreditStatus.CLEARED.value, cleared_at=None, deleted=False,
        )
        svc = object.__new__(ReferralService)
        svc._credits = AsyncMock()
        svc._credits.list_pending_due = AsyncMock(
            return_value=[_snapshot(db, status=ReferralCreditStatus.PENDING.value)]
        )
        svc._credits.claim_transition = fake_claim_transition({"rc-1": db})
        svc._users = AsyncMock()

        assert await svc.sweep_referral_credits() == 0
        svc._users.add_credit_balance.assert_not_called()
        assert events == []

    async def test_the_winner_adds_to_the_balance_in_sql(self, events):
        from main.app.domain.referral.service import ReferralService

        db = SimpleNamespace(
            id="rc-1", referrer_user_id="r-1", amount_minor=5_000,
            status=ReferralCreditStatus.PENDING.value, cleared_at=None, deleted=False,
        )
        svc = object.__new__(ReferralService)
        svc._credits = AsyncMock()
        svc._credits.list_pending_due = AsyncMock(return_value=[_snapshot(db)])
        svc._credits.claim_transition = fake_claim_transition({"rc-1": db})
        svc._users = AsyncMock()

        assert await svc.sweep_referral_credits() == 1
        svc._users.add_credit_balance.assert_awaited_once_with("r-1", 5_000)
        assert db.cleared_at is not None


# ── Workflow ──────────────────────────────────────────────────────


def _task(state=TaskState.PENDING, agent=None, in_pool=True):
    return SimpleNamespace(
        id="t-1", verification_id="v-1", role="FIELD", state=state.value,
        assigned_agent_id=agent, in_pool=in_pool, assignment_mode=None, decline_count=0,
        accepted_at=None, deleted=False,
    )


def _task_service(db_row, read):
    from main.app.domain.verification.task.service import VerificationTaskService

    svc = object.__new__(VerificationTaskService)
    svc._task_repo = AsyncMock()
    svc._task_repo.get_model = AsyncMock(return_value=read)
    svc._task_repo.count_active_for_agent = AsyncMock(return_value=0)
    svc._task_repo.claim_transition = fake_claim_transition({"t-1": db_row})
    svc._verification_repo = AsyncMock()
    svc._audit = MagicMock()
    svc._derive_and_persist = AsyncMock()
    return svc


class TestTasks:
    async def test_first_accept_of_a_pool_task_wins(self, monkeypatch):
        from main.app.domain.verification.task import service as task_module

        _locks(monkeypatch, task_module)
        db = _task(TaskState.ACCEPTED, agent="agent-1", in_pool=False)
        svc = _task_service(db, read=_snapshot(db, state=TaskState.PENDING.value, assigned_agent_id=None, in_pool=True))

        with pytest.raises(InvalidResourceStateException):
            await svc.accept("t-1", "agent-2")

        assert db.assigned_agent_id == "agent-1"
        svc._derive_and_persist.assert_not_called()

    async def test_capacity_is_checked_under_a_per_agent_lock(self, monkeypatch):
        from main.app.domain.verification.task import service as task_module

        order = []
        locks = _locks(monkeypatch, task_module, order)
        db = _task()
        svc = _task_service(db, read=_snapshot(db))

        async def _count(agent_id):
            order.append("count")
            return 0

        svc._task_repo.count_active_for_agent = AsyncMock(side_effect=_count)

        await svc.accept("t-1", "agent-1")

        assert locks == ["agent_tasks:agent-1"]
        assert order == ["lock:agent_tasks:agent-1", "count"]
        assert (db.state, db.assigned_agent_id, db.in_pool) == (TaskState.ACCEPTED.value, "agent-1", False)
        assert db.accepted_at is not None

    async def test_decline_counts_in_sql_and_frees_the_task(self):
        db = _task(TaskState.ACCEPTED, agent="agent-1", in_pool=False)
        svc = _task_service(db, read=_snapshot(db))

        await svc.decline("t-1", "agent-1", "busy")

        assert (db.state, db.assigned_agent_id, db.in_pool, db.decline_count) == (
            TaskState.PENDING.value, None, True, 1,
        )
        assert svc._task_repo.claim_transition.call_args.kwargs["increments"] == {"decline_count": 1}

    async def test_no_show_sweep_skips_a_task_the_agent_just_accepted(self):
        db = _task(TaskState.ACCEPTED, agent="agent-1", in_pool=False)
        svc = _task_service(db, read=None)
        svc._task_repo.list_accept_deadline_expired = AsyncMock(
            return_value=[_snapshot(db, state=TaskState.ASSIGNED.value)]
        )

        assert await svc.sweep_no_show() == 0
        assert db.state == TaskState.ACCEPTED.value
        svc._audit.schedule.assert_not_called()


class TestReviewDecisions:
    def _service(self, locked):
        from main.app.domain.verification.review.service import ReviewService

        svc = object.__new__(ReviewService)
        svc._verification_repo = AsyncMock()
        svc._verification_repo.get_model = AsyncMock(
            return_value=_snapshot(locked, status=VerificationStatus.UNDER_REVIEW.value)
        )
        svc._verification_repo.lock_model = AsyncMock(return_value=locked)
        svc._verification_repo.claim_transition = fake_claim_transition({"v-1": locked})
        svc._tasks = AsyncMock()
        svc._commissions = AsyncMock()
        svc._reports = AsyncMock()
        svc._payments = AsyncMock()
        svc._audit = MagicMock()
        return svc

    async def test_a_second_release_waits_for_the_first_then_is_refused(self):
        locked = _verification(VerificationStatus.COMPLETED)  # the first release committed
        svc = self._service(locked)

        with pytest.raises(InvalidResourceStateException):
            await svc.release("v-1", "admin-2")

        svc._verification_repo.lock_model.assert_awaited_once_with("v-1")
        svc._commissions.accrue.assert_not_called()
        svc._reports.release.assert_not_called()

    async def test_fail_loses_to_a_concurrent_release_and_refunds_nothing(self):
        locked = _verification(VerificationStatus.COMPLETED)
        svc = self._service(locked)

        with pytest.raises(InvalidResourceStateException):
            await svc.fail("v-1", "fraud", "admin-2")

        svc._payments.refund.assert_not_called()


class TestRecheck:
    def _service(self, db_row, read):
        from main.app.domain.verification.recheck.service import RecheckService

        svc = object.__new__(RecheckService)
        svc._recheck_repo = AsyncMock()
        svc._recheck_repo.get_model = AsyncMock(return_value=read)
        svc._recheck_repo.get_by_payment = AsyncMock(return_value=read)
        svc._recheck_repo.claim_transition = fake_claim_transition({"r-1": db_row})
        svc._payments = AsyncMock()
        svc._reviews = AsyncMock()
        svc._verification_repo = AsyncMock()
        svc._audit = MagicMock()
        svc._notify_decision = AsyncMock()
        return svc

    @staticmethod
    def _recheck(status):
        return SimpleNamespace(
            id="r-1", verification_id="v-1", customer_id="c-1", price_minor=1_000,
            status=status.value, scope_roles=["FIELD"], payment_id="pay-9", deleted=False,
        )

    async def test_a_second_approval_charges_nothing(self):
        from main.app.core.state.status import AgentRole

        db = self._recheck(RecheckStatus.APPROVED)
        svc = self._service(db, read=_snapshot(db, status=RecheckStatus.PENDING.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.admin_decide("r-1", DecideRecheckDto(approve=True, scope_roles=[AgentRole.FIELD]), "admin-2")

        svc._payments.initiate_secondary.assert_not_called()
        svc._notify_decision.assert_not_called()

    async def test_a_replayed_payment_reopens_the_tasks_once(self):
        db = self._recheck(RecheckStatus.STARTED)
        svc = self._service(db, read=_snapshot(db, status=RecheckStatus.APPROVED.value))

        await svc.on_payment_confirmed("pay-9")

        svc._reviews.reopen_task.assert_not_called()


class TestUpgrade:
    async def test_a_replayed_payment_applies_the_upgrade_once(self, events):
        from main.app.domain.verification.upgrade.service import UpgradeService

        db = SimpleNamespace(
            id="u-1", verification_id="v-1", customer_id="c-1", from_tier="BASIC", to_tier="STANDARD",
            status=UpgradeStatus.PAID.value, deleted=False,
        )
        svc = object.__new__(UpgradeService)
        svc._upgrade_repo = AsyncMock()
        svc._upgrade_repo.get_by_payment = AsyncMock(return_value=_snapshot(db, status=UpgradeStatus.PENDING.value))
        svc._upgrade_repo.claim_transition = fake_claim_transition({"u-1": db})
        svc._verification_repo = AsyncMock()
        svc._tasks = AsyncMock()
        svc._audit = MagicMock()

        await svc.on_payment_confirmed("pay-9")

        svc._verification_repo.update.assert_not_called()
        svc._tasks.prepare_for_paid.assert_not_called()


class TestDisputes:
    def _service(self):
        from main.app.domain.verification.dispute.service import DisputeService

        svc = object.__new__(DisputeService)
        svc._dispute_repo = AsyncMock()
        svc._verification_repo = AsyncMock()
        svc._verifications = AsyncMock()
        svc._commissions = AsyncMock()
        svc._payments = AsyncMock()
        svc._reviews = AsyncMock()
        svc._config = AsyncMock()
        svc._config.get_int = AsyncMock(return_value=5)
        svc._tasks = AsyncMock()
        svc._audit = MagicMock()
        svc._assert_within_window = AsyncMock()
        return svc

    async def test_two_concurrent_opens_freeze_commissions_once(self, events):
        from main.app.domain.verification.dispute.models import DisputeType, OpenDisputeDto

        db = _verification(VerificationStatus.DISPUTED)
        svc = self._service()
        svc._verifications.get_owned = AsyncMock(return_value=_snapshot(db, status=VerificationStatus.COMPLETED.value))
        svc._verification_repo.claim_transition = fake_claim_transition({"v-1": db})

        with pytest.raises(InvalidResourceStateException):
            await svc.open("v-1", "c-1", OpenDisputeDto(
                dispute_type=list(DisputeType)[0], description="the boundary is wrong",
            ))

        svc._commissions.freeze_for_verification.assert_not_called()
        svc._dispute_repo.create_return_model.assert_not_called()

    async def test_two_concurrent_resolutions_refund_once(self, events):
        db = SimpleNamespace(
            id="d-1", verification_id="v-1", customer_id="c-1", status=DisputeStatus.RESOLVED.value,
            deleted=False,
        )
        svc = self._service()
        svc._dispute_repo.get_model = AsyncMock(return_value=_snapshot(db, status=DisputeStatus.OPEN.value))
        svc._dispute_repo.claim_transition = fake_claim_transition({"d-1": db})
        svc._verification_repo.get_model = AsyncMock(return_value=_verification(VerificationStatus.DISPUTED))

        with pytest.raises(InvalidResourceStateException):
            await svc.resolve("d-1", ResolveDisputeDto(outcome=DisputeOutcome.FULL_REFUND, note="upheld"), "admin-2")

        svc._payments.refund.assert_not_called()
        svc._commissions.reverse_for_verification.assert_not_called()
        assert events == []


# ── Auth / admin ──────────────────────────────────────────────────


class TestPasswordReset:
    async def test_consume_is_the_conditional_update(self):
        from main.app.domain.user.auth.session.service import SessionService

        svc = object.__new__(SessionService)
        svc._reset_repo = AsyncMock()
        svc._reset_repo.consume = AsyncMock(side_effect=[SimpleNamespace(user_id="u-1"), None])

        assert (await svc.consume_password_reset_token("h")).user_id == "u-1"
        # The second of two concurrent submissions of one link finds it already used.
        assert await svc.consume_password_reset_token("h") is None


class TestAdminInvitations:
    def _service(self, db_row, read):
        from main.app.domain.user.admin_invitation.service import AdminInvitationService

        svc = object.__new__(AdminInvitationService)
        svc._invitation_repo = AsyncMock()
        svc._invitation_repo.get_by_token_hash = AsyncMock(return_value=read)
        svc._invitation_repo.get_model = AsyncMock(side_effect=[read, db_row])
        svc._invitation_repo.claim_transition = fake_claim_transition({"inv-1": db_row})
        svc._user_service = AsyncMock()
        svc._user_service.get_user_model = AsyncMock(return_value=SimpleNamespace(
            email="new.admin@example.com", user_type="USER",
        ))
        svc._audit_service = MagicMock()
        return svc

    @staticmethod
    def _invitation(status):
        return SimpleNamespace(
            id="inv-1", email_normalized="new.admin@example.com", sub_role="FINANCE",
            status=status.value, expires_at=Utils.datetime_now_plus(seconds=3600),
            accepted_at=None, accepted_by=None, deleted=False,
        )

    async def test_accept_loses_to_a_concurrent_revoke_and_elevates_no_one(self):
        db = self._invitation(AdminInvitationStatus.REVOKED)
        svc = self._service(db, read=_snapshot(db, status=AdminInvitationStatus.PENDING.value))

        with pytest.raises(InvalidTokenException):
            await svc.accept("raw-token", "u-1")

        svc._user_service.update_user.assert_not_called()

    async def test_revoke_cannot_undo_an_accepted_invitation(self):
        db = self._invitation(AdminInvitationStatus.ACCEPTED)
        svc = self._service(db, read=_snapshot(db, status=AdminInvitationStatus.PENDING.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.revoke("inv-1", "admin-1")
        assert db.status == AdminInvitationStatus.ACCEPTED.value

    async def test_revoking_twice_is_harmless(self):
        db = self._invitation(AdminInvitationStatus.REVOKED)
        svc = self._service(db, read=db)

        await svc.revoke("inv-1", "admin-1")


class TestPersonaGrant:
    async def test_the_grant_is_the_atomic_append(self):
        from main.app.domain.user.service import UserService

        svc = object.__new__(UserService)
        svc._user_repo = AsyncMock()
        svc._user_repo.get_model = AsyncMock(return_value=SimpleNamespace(personas=[UserPersona.CUSTOMER.value]))
        svc._user_validator = AsyncMock()

        await svc.add_persona("u-1", UserPersona.AGENT)

        svc._user_repo.add_persona.assert_awaited_once_with("u-1", UserPersona.AGENT)
        svc._user_repo.update.assert_not_called()


class TestDeviceSessions:
    USER_HEX = "0199a0000000700080000000000000aa"

    async def test_revoking_other_devices_and_rotating_take_the_same_user_lock(self, monkeypatch):
        import uuid

        from main.app.domain.user.auth.session import service as session_module
        from main.app.domain.user.auth.session.service import SessionService

        locks = _locks(monkeypatch, session_module)
        svc = object.__new__(SessionService)
        svc._device_repo = AsyncMock()
        svc._device_repo.list_for_user = AsyncMock(return_value=[])
        svc._device_repo.get_by_token_hash = AsyncMock(return_value=None)
        svc.build_session_dto = AsyncMock()
        user = SimpleNamespace(id=uuid.UUID(self.USER_HEX))

        await svc.revoke_all_other_devices(str(user.id), "hash-a")
        await svc.rotate_current_session(user, MagicMock(), "hash-a")

        # Either id form names the same lock, so the two always take turns.
        assert locks == [f"device_sessions:{self.USER_HEX}"] * 2


class TestConsentOrdering:
    async def test_a_decision_is_stamped_on_the_locked_row(self):
        from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsent, WhatsAppConsentSource
        from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService

        row = WhatsAppConsent(user_id="u-1")
        svc = object.__new__(WhatsAppConsentService)
        svc._whatsapp_consent_repo = MagicMock()
        svc._whatsapp_consent_repo.insert_or_get = AsyncMock(return_value=(row, False))
        svc._whatsapp_consent_repo.lock_model = AsyncMock(return_value=row)
        svc._audit = MagicMock()

        await svc.set_consents("u-1", True, False, WhatsAppConsentSource.PAY_SCREEN)

        # A STOP racing this save waits for the lock, then stamps against what this one
        # wrote — so whichever decision arrives second reads as the later one.
        svc._whatsapp_consent_repo.lock_model.assert_awaited_once()
        svc._whatsapp_consent_repo.apply.assert_called()


# ── Chargebacks and commissions ───────────────────────────────────


class TestChargebacks:
    def _service(self, db_row, read):
        from main.app.domain.payment.chargeback.service import ChargebackService

        svc = object.__new__(ChargebackService)
        svc._chargeback_repo = AsyncMock()
        svc._chargeback_repo.get_model = AsyncMock(return_value=read)
        svc._chargeback_repo.claim_transition = fake_claim_transition({"cb-1": db_row})
        svc._payment_repo = AsyncMock()
        svc._commissions = AsyncMock()
        svc._audit = MagicMock()
        return svc

    @staticmethod
    def _chargeback(status):
        return SimpleNamespace(
            id="cb-1", payment_id="pay-1", verification_id="v-1", amount_minor=10_000,
            status=status.value, resolved_at=None, deleted=False,
        )

    async def test_a_loss_racing_a_win_reverses_nothing(self):
        from main.app.domain.payment.chargeback.models import ChargebackStatus

        db = self._chargeback(ChargebackStatus.WON)  # the other admin resolved it first
        svc = self._service(db, read=_snapshot(db, status=ChargebackStatus.REBUTTAL_SUBMITTED.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.resolve("cb-1", won=False, admin_id="admin-2")

        svc._commissions.reverse_for_verification.assert_not_called()
        svc._payment_repo.update.assert_not_called()

    async def test_resolution_is_stamped_in_the_claim(self):
        from main.app.domain.payment.chargeback.models import ChargebackStatus

        db = self._chargeback(ChargebackStatus.FLAGGED)
        svc = self._service(db, read=_snapshot(db))

        await svc.resolve("cb-1", won=True, admin_id="admin-1")

        assert db.status == ChargebackStatus.WON.value
        assert db.resolved_at is not None
        svc._commissions.unfreeze_for_verification.assert_awaited_once()


class TestCommissions:
    def _service(self, rows_by_id, listed):
        from main.app.domain.commission.service import CommissionService

        svc = object.__new__(CommissionService)
        svc._commission_repo = AsyncMock()
        svc._commission_repo.list_for_verification_in_status = AsyncMock(return_value=listed)
        svc._commission_repo.claim_transition = fake_claim_transition(rows_by_id)
        svc._audit = MagicMock()
        return svc

    @staticmethod
    def _commission(status, frozen_from=None):
        return SimpleNamespace(id="c-1", status=status.value, frozen_from_status=frozen_from, deleted=False)

    async def test_an_unfreeze_racing_a_reversal_cannot_revive_the_commission(self):
        from main.app.domain.commission.models import CommissionStatus

        db = self._commission(CommissionStatus.REVERSED, frozen_from=CommissionStatus.AVAILABLE.value)
        svc = self._service({"c-1": db}, listed=[_snapshot(db, status=CommissionStatus.FROZEN.value)])

        assert await svc.unfreeze_for_verification("v-1", actor_id="admin-1") == 0
        assert db.status == CommissionStatus.REVERSED.value

    async def test_freeze_records_the_status_the_row_really_had(self):
        from main.app.domain.commission.models import CommissionStatus

        # Listed as CLEARING, but the clearing sweep moved it to AVAILABLE meanwhile.
        db = self._commission(CommissionStatus.AVAILABLE)
        svc = self._service({"c-1": db}, listed=[_snapshot(db, status=CommissionStatus.CLEARING.value)])

        assert await svc.freeze_for_verification("v-1", actor_id="admin-1") == 1
        assert db.status == CommissionStatus.FROZEN.value
        assert db.frozen_from_status == CommissionStatus.AVAILABLE.value


# ── Admin decisions ───────────────────────────────────────────────


class TestAgentApplicationDecisions:
    def _service(self, db_row, read):
        from main.app.domain.user.agent.service import AgentService

        svc = object.__new__(AgentService)
        svc._profile_repo = AsyncMock()
        svc._profile_repo.get_model = AsyncMock(return_value=read)
        svc._profile_repo.claim_transition = fake_claim_transition({"prof-1": db_row})
        svc._credential_repo = AsyncMock()
        svc._credential_repo.list_for_user = AsyncMock(return_value=[])
        svc._audit_service = MagicMock()
        svc.get_application_detail = AsyncMock()
        return svc

    @staticmethod
    def _profile(status):
        return SimpleNamespace(
            id="prof-1", user_id="u-1", roles=["FIELD"], status=status.value, approved_roles=None,
            rejection_reason=None, reviewed_by=None, reviewed_at=None, deleted=False,
        )

    async def test_approval_racing_a_rejection_verifies_nothing(self):
        from main.app.domain.user.agent.models import ApproveAgentApplicationDto
        from main.app.domain.user.agent.profile.models import AgentApplicationStatus

        db = self._profile(AgentApplicationStatus.REJECTED)
        svc = self._service(db, read=_snapshot(db, status=AgentApplicationStatus.PENDING.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.approve_application("prof-1", ApproveAgentApplicationDto(), "admin-2")

        svc._credential_repo.update.assert_not_called()
        assert db.status == AgentApplicationStatus.REJECTED.value

    async def test_a_decision_is_stamped_in_the_claim(self):
        from main.app.domain.user.agent.models import RejectAgentApplicationDto
        from main.app.domain.user.agent.profile.models import AgentApplicationStatus

        db = self._profile(AgentApplicationStatus.PENDING)
        svc = self._service(db, read=_snapshot(db))

        await svc.reject_application("prof-1", RejectAgentApplicationDto(reason="licence expired"), "admin-1")

        assert (db.status, db.rejection_reason, db.reviewed_by) == (
            AgentApplicationStatus.REJECTED.value, "licence expired", "admin-1",
        )
        assert db.reviewed_at is not None


class TestErasure:
    def _service(self, db_row, read):
        from main.app.domain.compliance.erasure.service import ErasureService

        svc = object.__new__(ErasureService)
        svc._erasure_repo = AsyncMock()
        svc._erasure_repo.get_model = AsyncMock(side_effect=[read, db_row])
        svc._erasure_repo.claim_transition = fake_claim_transition({"er-1": db_row})
        svc._pseudonymiser = MagicMock()
        svc._pseudonymiser.token_for = MagicMock(return_value="tok")
        svc._pseudonymiser.pseudonymise = AsyncMock(return_value=["users"])
        svc._audit = MagicMock()
        svc._notify = AsyncMock()
        return svc

    @staticmethod
    def _request(status):
        return SimpleNamespace(
            id="er-1", subject_user_id="u-1", status=status.value, reviewed_by_user_id=None,
            reviewed_at=None, decision_note=None, executed_at=None, pseudonym_token=None, deleted=False,
        )

    async def test_a_rejection_racing_an_approval_notifies_no_one(self):
        from main.app.core.state.status import ErasureRequestState

        db = self._request(ErasureRequestState.APPROVED)
        svc = self._service(db, read=_snapshot(db, status=ErasureRequestState.PENDING.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.reject("er-1", "admin-2", "no")

        svc._notify.assert_not_called()
        assert db.status == ErasureRequestState.APPROVED.value

    async def test_a_concurrent_execution_pseudonymises_once(self):
        from main.app.core.state.status import ErasureRequestState

        db = self._request(ErasureRequestState.EXECUTED)
        svc = self._service(db, read=_snapshot(db, status=ErasureRequestState.APPROVED.value))

        out = await svc.execute("er-1", "admin-2")

        assert out.status == ErasureRequestState.EXECUTED.value
        svc._pseudonymiser.pseudonymise.assert_not_called()
