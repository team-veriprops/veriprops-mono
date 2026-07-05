"""SlaMonitorService (§12.2, D23): the SLA-breach sweep publishes once per overdue
verification and is idempotent on an existing SLA-breach notification."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

import main.app.domain.verification.sla_monitor as sla_monitor_mod
from main.app.core.events.events import EventType
from main.app.domain.verification.sla_monitor import SlaMonitorService
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


def _service(overdue, already_notified):
    svc = object.__new__(SlaMonitorService)
    svc._verifications = MagicMock()
    svc._verifications.list_active_overdue = AsyncMock(return_value=overdue)
    svc._notifications = MagicMock()
    svc._notifications.exists_for_ref = AsyncMock(return_value=already_notified)
    return svc


def _verification(vid_id="v-1"):
    return SimpleNamespace(id=vid_id, vid="VP-ABC", customer_id="cust-1")


async def test_publishes_sla_breach_for_new_overdue(monkeypatch):
    published = []
    monkeypatch.setattr(
        sla_monitor_mod, "publish_domain_event",
        AsyncMock(side_effect=lambda e: published.append(e)),
    )
    svc = _service(overdue=[_verification()], already_notified=False)

    flagged = await svc.sweep_sla_breaches()

    assert flagged == 1
    assert published[0].type == EventType.SLA_BREACHED
    assert published[0].recipient_user_ids == ("cust-1",)


async def test_skips_already_notified_verifications(monkeypatch):
    published = []
    monkeypatch.setattr(
        sla_monitor_mod, "publish_domain_event",
        AsyncMock(side_effect=lambda e: published.append(e)),
    )
    svc = _service(overdue=[_verification()], already_notified=True)

    flagged = await svc.sweep_sla_breaches()

    assert flagged == 0
    assert published == []
