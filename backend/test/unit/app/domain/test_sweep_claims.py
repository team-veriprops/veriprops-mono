"""Sweeps act on each row once, even when two runs overlap.

The job lock keeps the scheduler to one worker, but the same sweeps are also reachable from
admin endpoints, and a run can outlast its interval. So each sweep claims every row before
acting on it: a row another run already took is skipped, and no message, notification or
balance change happens twice.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.core.state.status import TaskState, VerificationStatus
from main.app.domain.broadcast.models import BroadcastStatus
from main.app.domain.commission.models import CommissionStatus
from main.app.domain.message.repo import MessageRepo
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from main.appodus_utils.integrations.messaging.models import (
    EmailPayload,
    MessageChannel,
    MessageRecipient,
    MessageStatus,
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
    published = []

    async def _publish(event):
        published.append(event)

    from main.app.domain.broadcast import service as broadcast_module
    from main.app.domain.earnings import service as earnings_module
    from main.app.domain.verification import service as verification_module
    for module in (broadcast_module, earnings_module, verification_module):
        monkeypatch.setattr(module, "publish_domain_event", _publish)
    return published


def _snapshot(row, **stale):
    return SimpleNamespace(**{**vars(row), **stale})


# ── Message retries ───────────────────────────────────────────────


def _retrying(row_id):
    return UpsertMessageDto(
        id=row_id, channel=MessageChannel.EMAIL, to=MessageRecipient(recipient="user@example.com"),
        payload=EmailPayload(subject="Hello", html="<p>Hi</p>"), status=MessageStatus.RETRYING,
        retry_count=0, next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1), extras={},
    )


class TestMessageRetries:
    async def test_only_leased_rows_are_sent(self):
        from main.appodus_utils.integrations.messaging.service import MessagingService
        from main.appodus_utils.integrations.messaging.services.rate_limiting import Throttler

        ours, theirs = _retrying("a" * 32), _retrying("b" * 32)
        svc = object.__new__(MessagingService)
        svc.router = AsyncMock()
        svc.router.send_message = AsyncMock(side_effect=lambda m: m)
        svc.message_service = AsyncMock()
        svc.message_service.get_retry_ready_messages = AsyncMock(return_value=SimpleNamespace(items=[ours, theirs]))
        # The other run leased the second row first.
        svc.message_service.lease_retry = AsyncMock(side_effect=lambda message_id, now, until: message_id == ours.id)
        svc.rate_limiter = AsyncMock()
        svc.throttler = Throttler(rps_limit=10_000)

        stats = await svc.process_retries()

        assert [c.args[0] for c in svc.router.send_message.await_args_list] == [ours]
        assert stats["processed"] == 1

    async def test_the_lease_is_one_conditional_update(self, mock_db_session):
        result = MagicMock()
        result.scalar.return_value = None
        mock_db_session.execute = AsyncMock(return_value=result)
        now = datetime.now(timezone.utc)

        leased = await MessageRepo(db=None).lease_retry(uuid.uuid4().hex, now, now + timedelta(minutes=5))

        assert leased is False
        stmt = mock_db_session.execute.await_args.args[0]
        sql = " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())
        assert sql.startswith("UPDATE messages SET next_retry_at=")
        assert "messages.status = %(status_1)s" in sql
        # Only a row still due is leased; one already leased by another run is in the future.
        assert "messages.next_retry_at <= %(next_retry_at_1)s" in sql
        assert "RETURNING messages.id" in sql


# ── Broadcasts ────────────────────────────────────────────────────


def _broadcast(status):
    return SimpleNamespace(
        id="b-1", audience="ALL", subject="s", body="b", status=status.value,
        sent_at=None, recipient_count=None, deleted=False,
    )


def _broadcast_service(db_row, read):
    from main.app.domain.broadcast.service import BroadcastService

    svc = object.__new__(BroadcastService)
    svc._broadcast_repo = AsyncMock()
    svc._broadcast_repo.get_model = AsyncMock(side_effect=[read, db_row, db_row])
    svc._broadcast_repo.list_due_scheduled = AsyncMock(return_value=[read])
    svc._broadcast_repo.claim_transition = fake_claim_transition({"b-1": db_row})
    svc._users = AsyncMock()
    svc._users.list_recipient_rows = AsyncMock(return_value=[("u-1", "USER", ["CUSTOMER"])])
    svc._audit = MagicMock()
    return svc


class TestBroadcasts:
    async def test_a_broadcast_sent_by_an_overlapping_run_is_not_sent_again(self, events):
        db = _broadcast(BroadcastStatus.SENT)
        svc = _broadcast_service(db, read=_snapshot(db, status=BroadcastStatus.SCHEDULED.value))

        assert await svc.sweep_scheduled_broadcasts() == 0
        assert events == []

    async def test_send_now_racing_the_sweep_fans_out_once(self, events):
        db = _broadcast(BroadcastStatus.SENT)
        svc = _broadcast_service(db, read=_snapshot(db, status=BroadcastStatus.SCHEDULED.value))

        out = await svc.send_now("b-1", "admin-1")

        assert out.status == BroadcastStatus.SENT.value
        assert events == []

    async def test_the_sender_claims_then_records_the_audience(self, events):
        db = _broadcast(BroadcastStatus.SCHEDULED)
        svc = _broadcast_service(db, read=_snapshot(db))

        assert await svc.sweep_scheduled_broadcasts() == 1
        assert (db.status, db.recipient_count) == (BroadcastStatus.SENT.value, 1)
        assert db.sent_at is not None
        assert len(events) == 1

    async def test_cancel_cannot_land_on_a_broadcast_just_sent(self):
        db = _broadcast(BroadcastStatus.SENT)
        svc = _broadcast_service(db, read=_snapshot(db, status=BroadcastStatus.SCHEDULED.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("b-1", "admin-1")
        assert db.status == BroadcastStatus.SENT.value


# ── Commission clearance ──────────────────────────────────────────


class TestCommissionClearance:
    def _service(self, db_row, clearing=(), reserve=()):
        from main.app.domain.earnings.service import EarningsService

        svc = object.__new__(EarningsService)
        svc._commissions = AsyncMock()
        svc._commissions.list_clearing_due = AsyncMock(return_value=list(clearing))
        svc._commissions.list_reserve_due = AsyncMock(return_value=list(reserve))
        svc._commissions.claim_transition = fake_claim_transition({"c-1": db_row})
        return svc

    @staticmethod
    def _commission(status, reserve_released_at=None):
        return SimpleNamespace(
            id="c-1", agent_id="a-1", status=status.value, reserve_released_at=reserve_released_at, deleted=False,
        )

    async def test_a_commission_frozen_meanwhile_is_not_made_available(self, events):
        db = self._commission(CommissionStatus.FROZEN)
        svc = self._service(db, clearing=[_snapshot(db, status=CommissionStatus.CLEARING.value)])

        assert await svc.sweep_cleared() == 0
        assert db.status == CommissionStatus.FROZEN.value
        assert events == []

    async def test_a_reserve_is_released_once(self, events):
        released = datetime.now(timezone.utc)
        db = self._commission(CommissionStatus.AVAILABLE, reserve_released_at=released)
        svc = self._service(db, reserve=[_snapshot(db, reserve_released_at=None)])

        assert await svc.sweep_cleared() == 0
        assert db.reserve_released_at == released
        assert events == []

    async def test_the_winner_clears_and_notifies(self, events):
        db = self._commission(CommissionStatus.CLEARING)
        svc = self._service(db, clearing=[_snapshot(db)])

        assert await svc.sweep_cleared() == 1
        assert db.status == CommissionStatus.AVAILABLE.value
        assert len(events) == 1


# ── Abandoned drafts and pool starvation ──────────────────────────


class TestAbandonedDrafts:
    async def test_a_draft_reminded_by_an_overlapping_run_is_not_emailed_again(self, events):
        from main.app.domain.verification.service import VerificationService

        db = SimpleNamespace(
            id="v-1", vid="VP-1", customer_id="c-1", status=VerificationStatus.SUBMITTED.value,
            recovery_reminded_at=datetime.now(timezone.utc), deleted=False,
        )
        svc = object.__new__(VerificationService)
        svc._verification_repo = AsyncMock()
        svc._verification_repo.list_abandoned_drafts = AsyncMock(return_value=[_snapshot(db, recovery_reminded_at=None)])
        svc._verification_repo.claim_transition = fake_claim_transition({"v-1": db})

        assert await svc.sweep_abandoned_drafts() == 0
        assert events == []


class TestPoolStarvation:
    async def test_a_task_escalated_by_an_overlapping_run_is_not_escalated_again(self):
        from main.app.domain.verification.task.service import VerificationTaskService

        db = SimpleNamespace(
            id="t-1", role="FIELD", state=TaskState.PENDING.value, in_pool=False,
            remote_bonus_minor=None, deleted=False,
        )
        svc = object.__new__(VerificationTaskService)
        svc._task_repo = AsyncMock()
        svc._task_repo.list_pool_expired = AsyncMock(return_value=[_snapshot(db, in_pool=True)])
        svc._task_repo.claim_transition = fake_claim_transition({"t-1": db})
        svc._audit = MagicMock()

        assert await svc.sweep_pool_starvation() == 0
        svc._audit.schedule.assert_not_called()
