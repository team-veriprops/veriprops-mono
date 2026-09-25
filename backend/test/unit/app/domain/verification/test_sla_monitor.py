"""SlaMonitorService (§12.2, D23): the SLA-breach sweep notifies once per overdue verification.

"Once" is a claim on the verification itself: the sweep stamps `sla_breach_notified_at` in one
conditional update before it publishes, so a scheduled run and an admin-triggered run landing
together notify once — and a notification deleted later can never cause a second one. (It used to
check whether a notification already existed, which two overlapping runs both passed.)
"""
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.dialects import postgresql

import main.app.domain.verification.sla_monitor as sla_monitor_mod
from main.app.core.events.events import EventType
from main.app.core.state.status import VerificationStatus
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.sla_monitor import SlaMonitorService
from main.appodus_utils.db.session import db_session_ctx
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
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture
def published(monkeypatch):
    events = []
    monkeypatch.setattr(
        sla_monitor_mod, "publish_domain_event", AsyncMock(side_effect=lambda e: events.append(e)),
    )
    return events


def _verification(notified_at=None):
    return SimpleNamespace(
        id="v-1", vid="VP-ABC", customer_id="cust-1", status=VerificationStatus.IN_PROGRESS.value,
        sla_breach_notified_at=notified_at, deleted=False,
    )


def _service(listed, db_row, admins=()):
    svc = object.__new__(SlaMonitorService)
    svc._verifications = MagicMock()
    svc._verifications.list_active_overdue = AsyncMock(return_value=listed)
    svc._verifications.claim_transition = fake_claim_transition({"v-1": db_row})
    svc._users = MagicMock()
    svc._users.list_admins = AsyncMock(return_value=[SimpleNamespace(id=a) for a in admins])
    return svc


async def test_an_overdue_verification_is_claimed_then_announced(published):
    row = _verification()
    svc = _service(listed=[row], db_row=row, admins=["admin-1"])

    assert await svc.sweep_sla_breaches() == 1

    assert row.sla_breach_notified_at is not None
    assert published[0].type == EventType.SLA_BREACHED
    # §12.2: the customer AND the ops team are notified (G3).
    assert published[0].recipient_user_ids == ("cust-1", "admin-1")


async def test_a_verification_an_overlapping_run_claimed_is_not_announced_again(published):
    from datetime import datetime, timezone

    db = _verification(notified_at=datetime.now(timezone.utc))  # the other run got there first
    listed = SimpleNamespace(**{**vars(db), "sla_breach_notified_at": None})
    svc = _service(listed=[listed], db_row=db)

    assert await svc.sweep_sla_breaches() == 0
    assert published == []


async def test_nothing_overdue_publishes_nothing(published):
    svc = _service(listed=[], db_row=None)

    assert await svc.sweep_sla_breaches() == 0
    assert published == []


async def test_the_source_query_skips_verifications_already_announced(mock_db_session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db_session.execute = AsyncMock(return_value=result)

    await VerificationRepo(db=None).list_active_overdue([VerificationStatus.IN_PROGRESS.value], date(2026, 9, 25))

    stmt = mock_db_session.execute.await_args.args[0]
    sql = " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())
    assert "verifications.sla_breach_notified_at IS NULL" in sql
