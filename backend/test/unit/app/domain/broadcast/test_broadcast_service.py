"""BroadcastService (§18.1, D37) — compose/send/audience-resolution/sweep, repos mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.domain.broadcast import service as broadcast_module
from main.app.domain.broadcast.models import BroadcastAudience, BroadcastStatus, ComposeBroadcastDto
from main.app.domain.broadcast.service import BroadcastService
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.appodus_utils import Utils
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


@pytest.fixture(autouse=True)
def stub_publish(monkeypatch):
    published = []
    monkeypatch.setattr(broadcast_module, "publish_domain_event",
                        AsyncMock(side_effect=lambda e: published.append(e)))
    return published


# (user_id, user_type, personas)
_USERS = [
    ("u-admin", UserType.ADMIN.value, []),
    ("u-cust", UserType.USER.value, [UserPersona.CUSTOMER.value]),
    ("u-agent", UserType.USER.value, [UserPersona.AGENT.value]),
    ("u-both", UserType.USER.value, [UserPersona.CUSTOMER.value, UserPersona.AGENT.value]),
]


def _make_service():
    svc = object.__new__(BroadcastService)
    svc._repo = AsyncMock()
    svc._users = AsyncMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()
    svc._users.list_recipient_rows = AsyncMock(return_value=_USERS)
    return svc


class TestCompose:
    async def test_no_schedule_is_draft(self):
        svc = _make_service()
        svc._repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="b-1", **dto.model_dump()))
        b = await svc.compose(ComposeBroadcastDto(
            audience=BroadcastAudience.ALL, subject="Hi", body="Body"), "admin-1")
        assert b.status == BroadcastStatus.DRAFT

    async def test_with_schedule_is_scheduled(self):
        svc = _make_service()
        svc._repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="b-1", **dto.model_dump()))
        when = Utils.datetime_now()
        b = await svc.compose(ComposeBroadcastDto(
            audience=BroadcastAudience.CUSTOMERS, subject="Hi", body="B", scheduled_at=when), "admin-1")
        assert b.status == BroadcastStatus.SCHEDULED


class TestPreview:
    async def test_audience_counts(self):
        svc = _make_service()
        assert (await svc.preview(BroadcastAudience.ALL)).recipient_count == 4
        assert (await svc.preview(BroadcastAudience.ADMINS)).recipient_count == 1
        assert (await svc.preview(BroadcastAudience.CUSTOMERS)).recipient_count == 2  # cust + both
        assert (await svc.preview(BroadcastAudience.AGENTS)).recipient_count == 2     # agent + both


class TestSendNow:
    async def test_fans_out_and_marks_sent(self, stub_publish):
        svc = _make_service()
        row = SimpleNamespace(id="b-1", audience=BroadcastAudience.CUSTOMERS.value,
                              subject="S", body="B", status=BroadcastStatus.DRAFT.value,
                              sent_at=None, recipient_count=0)
        svc._repo.get_model = AsyncMock(return_value=row)
        await svc.send_now("b-1", "admin-1")
        assert row.status == BroadcastStatus.SENT.value
        assert row.recipient_count == 2
        assert stub_publish[0].type == EventType.BROADCAST_ANNOUNCEMENT
        assert set(stub_publish[0].recipient_user_ids) == {"u-cust", "u-both"}

    async def test_idempotent_when_already_sent(self, stub_publish):
        svc = _make_service()
        row = SimpleNamespace(id="b-1", audience=BroadcastAudience.ALL.value, subject="S",
                              body="B", status=BroadcastStatus.SENT.value, sent_at=None, recipient_count=0)
        svc._repo.get_model = AsyncMock(return_value=row)
        await svc.send_now("b-1", "admin-1")
        assert stub_publish == []


class TestSweep:
    async def test_sends_due_scheduled(self, stub_publish):
        svc = _make_service()
        due = SimpleNamespace(id="b-1", audience=BroadcastAudience.ADMINS.value, subject="S",
                              body="B", status=BroadcastStatus.SCHEDULED.value, sent_at=None, recipient_count=0)
        svc._repo.list_due_scheduled = AsyncMock(return_value=[due])
        svc._repo.get_model = AsyncMock(return_value=due)
        sent = await svc.sweep_scheduled_broadcasts()
        assert sent == 1
        assert due.status == BroadcastStatus.SENT.value
