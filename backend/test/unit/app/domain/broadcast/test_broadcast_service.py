"""BroadcastService (§18.1, D37) — compose, preview, send, cancel, and the paged fan-out.

A send claims the broadcast DRAFT/SCHEDULED → SENDING and records its audience size; the
fan-out then walks the audience in keyset pages. Each page is one claim on the broadcast's
cursor (so two runners never send the same page) plus **one** BROADCAST_ANNOUNCEMENT event for
that page's recipients. The last page moves the broadcast to SENT. "Send now" runs the first
page inline, in a savepoint: a page that fails there rolls back alone and is retried by the
next tick from the same cursor.
"""
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.core.events import EventType
from main.app.domain.broadcast import service as broadcast_module
from main.app.domain.broadcast.models import (
    BroadcastAction,
    BroadcastAudience,
    BroadcastStatus,
    ComposeBroadcastDto,
    allowed_actions,
)
from main.app.domain.broadcast.service import BroadcastService
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)
from test.utils.repo_fakes import fake_claim_transition

# (user_id, user_type, personas), already in id order.
_USERS = [
    ("u-1", UserType.ADMIN.value, []),
    ("u-2", UserType.USER.value, [UserPersona.CUSTOMER.value]),
    ("u-3", UserType.USER.value, [UserPersona.AGENT.value]),
    ("u-4", UserType.USER.value, [UserPersona.CUSTOMER.value, UserPersona.AGENT.value]),
    ("u-5", UserType.USER.value, [UserPersona.CUSTOMER.value]),
]


class FakeUsers:
    """The keyset recipient query over `_USERS`, filtered the way the SQL filters."""

    @staticmethod
    def _match(user_type, personas, want_type, want_persona) -> bool:
        return (want_type is None or user_type == want_type.value) and (
            want_persona is None or want_persona.value in personas)

    async def list_recipient_ids_page(self, after: Optional[str], limit: int, *, user_type=None, persona=None):
        ids = [uid for uid, ut, ps in _USERS if self._match(ut, ps, user_type, persona)]
        return [uid for uid in ids if after is None or uid > after][:limit]

    async def count_recipients(self, *, user_type=None, persona=None) -> int:
        return sum(1 for _, ut, ps in _USERS if self._match(ut, ps, user_type, persona))


@pytest.fixture(autouse=True)
def published(monkeypatch):
    events = []
    monkeypatch.setattr(broadcast_module, "publish_domain_event",
                        AsyncMock(side_effect=lambda e: events.append(e)))
    return events


@pytest.fixture(autouse=True)
def page_size(monkeypatch):
    monkeypatch.setattr(settings, "BROADCAST_FANOUT_PAGE_SIZE", 2)


@pytest.fixture(autouse=True)
def savepoints():
    """`begin_nested` on the context session; records each savepoint and whether it rolled back."""
    entered: List[str] = []

    class _Savepoint:
        async def __aenter__(self):
            entered.append("open")

        async def __aexit__(self, exc_type, exc, tb):
            entered.append("rolled back" if exc_type else "released")
            return False

    db_session_ctx.get().begin_nested = lambda: _Savepoint()
    return entered


def _row(status=BroadcastStatus.DRAFT, audience=BroadcastAudience.ALL, **over):
    base = dict(id="b-1", audience=audience.value, subject="S", body="B", status=status.value,
                sent_at=None, recipient_count=0, recipients_enqueued=0, fanout_cursor=None, deleted=False)
    base.update(over)
    return SimpleNamespace(**base)


def _service(row=None):
    svc = object.__new__(BroadcastService)
    svc._broadcast_repo = AsyncMock()
    svc._broadcast_repo.get_model = AsyncMock(return_value=row)
    svc._broadcast_repo.oldest_sending = AsyncMock(
        side_effect=lambda: row if row is not None and row.status == BroadcastStatus.SENDING.value else None)
    svc._broadcast_repo.claim_transition = fake_claim_transition(lambda _id: row)
    svc._users = FakeUsers()
    svc._audit = MagicMock()
    return svc


def _recipients(events):
    return [list(e.recipient_user_ids) for e in events]


class TestCompose:
    async def test_no_schedule_is_draft(self):
        svc = _service()
        svc._broadcast_repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="b-1", **dto.model_dump()))
        b = await svc.compose(ComposeBroadcastDto(audience=BroadcastAudience.ALL, subject="Hi", body="Body"), "admin-1")
        assert b.status == BroadcastStatus.DRAFT

    async def test_with_schedule_is_scheduled(self):
        svc = _service()
        svc._broadcast_repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="b-1", **dto.model_dump()))
        b = await svc.compose(ComposeBroadcastDto(
            audience=BroadcastAudience.CUSTOMERS, subject="Hi", body="B", scheduled_at=Utils.datetime_now()), "admin-1")
        assert b.status == BroadcastStatus.SCHEDULED


class TestPreview:
    @pytest.mark.parametrize("audience, count", [
        (BroadcastAudience.ALL, 5),
        (BroadcastAudience.ADMINS, 1),
        (BroadcastAudience.CUSTOMERS, 3),   # u-2, u-4, u-5
        (BroadcastAudience.AGENTS, 2),      # u-3, u-4
    ])
    async def test_audience_counts(self, audience, count):
        assert (await _service().preview(audience)).recipient_count == count


class TestSendNow:
    async def test_claims_sending_records_the_audience_and_sends_the_first_page_inline(self, published, savepoints):
        row = _row()
        await _service(row).send_now("b-1", "admin-1")

        assert row.status == BroadcastStatus.SENDING.value
        assert row.recipient_count == 5
        assert _recipients(published) == [["u-1", "u-2"]]
        assert published[0].type == EventType.BROADCAST_ANNOUNCEMENT
        assert row.fanout_cursor == "u-2" and row.recipients_enqueued == 2
        assert savepoints == ["open", "released"]

    async def test_an_audience_within_one_page_is_sent_in_the_request(self, published):
        row = _row(audience=BroadcastAudience.ADMINS)
        await _service(row).send_now("b-1", "admin-1")

        assert row.status == BroadcastStatus.SENT.value
        assert row.sent_at is not None
        assert _recipients(published) == [["u-1"]]
        assert row.recipients_enqueued == row.recipient_count == 1

    async def test_a_failed_inline_page_leaves_it_sending_for_the_tick(self, monkeypatch, published, savepoints):
        row = _row()
        svc = _service(row)
        monkeypatch.setattr(broadcast_module, "publish_domain_event", AsyncMock(side_effect=RuntimeError("boom")))

        result = await svc.send_now("b-1", "admin-1")  # the request still succeeds

        assert result.status == BroadcastStatus.SENDING.value
        assert savepoints == ["open", "rolled back"]

    async def test_resending_a_sending_or_sent_broadcast_fans_out_nothing(self, published):
        for status in (BroadcastStatus.SENDING, BroadcastStatus.SENT):
            await _service(_row(status)).send_now("b-1", "admin-1")
        assert published == []

    async def test_a_cancelled_broadcast_refuses_to_send(self):
        with pytest.raises(InvalidResourceStateException):
            await _service(_row(BroadcastStatus.CANCELLED)).send_now("b-1", "admin-1")


class TestFanOut:
    async def test_pages_walk_the_audience_once_and_finish_sent(self, published):
        row = _row(BroadcastStatus.SENDING, recipient_count=5)
        svc = _service(row)

        while await svc.fanout_next_page():
            pass

        assert _recipients(published) == [["u-1", "u-2"], ["u-3", "u-4"], ["u-5"]]
        assert row.status == BroadcastStatus.SENT.value
        assert row.recipients_enqueued == 5

    async def test_an_audience_that_fills_its_last_page_exactly_finishes_on_an_empty_page(self, published):
        row = _row(BroadcastStatus.SENDING, audience=BroadcastAudience.AGENTS, recipient_count=2)
        svc = _service(row)

        assert await svc.fanout_next_page() is True     # u-3, u-4: a full page, maybe more
        assert row.status == BroadcastStatus.SENDING.value
        assert await svc.fanout_next_page() is True     # empty: done
        assert row.status == BroadcastStatus.SENT.value
        assert await svc.fanout_next_page() is False    # nothing left to send
        assert _recipients(published) == [["u-3", "u-4"]]

    async def test_a_page_another_runner_already_sent_is_not_sent_again(self, published):
        db = _row(BroadcastStatus.SENDING, fanout_cursor="u-2", recipients_enqueued=2)
        svc = _service(db)
        # This runner read the broadcast before the other one moved the cursor.
        svc._broadcast_repo.oldest_sending = AsyncMock(return_value=_row(BroadcastStatus.SENDING))

        assert await svc.fanout_next_page() is False
        assert published == []

    async def test_a_cancelled_broadcast_stops_between_pages(self, published):
        row = _row(BroadcastStatus.SENDING)
        svc = _service(row)
        await svc.fanout_next_page()
        await svc.cancel("b-1", "admin-1")

        assert await svc.fanout_next_page() is False
        assert row.status == BroadcastStatus.CANCELLED.value
        assert _recipients(published) == [["u-1", "u-2"]]


class TestScheduledSweep:
    async def test_due_scheduled_broadcasts_start_sending(self):
        due = _row(BroadcastStatus.SCHEDULED)
        svc = _service(due)
        svc._broadcast_repo.list_due_scheduled = AsyncMock(return_value=[due])

        assert await svc.sweep_scheduled_broadcasts() == 1
        assert due.status == BroadcastStatus.SENDING.value
        assert due.recipient_count == 5

    async def test_the_admin_trigger_starts_and_fans_out(self, published):
        due = _row(BroadcastStatus.SCHEDULED)
        svc = _service(due)
        svc._broadcast_repo.list_due_scheduled = AsyncMock(return_value=[due])

        outcome = await svc.run_scheduled_sweep()

        assert outcome == {"started": 1, "pages": 3}
        assert due.status == BroadcastStatus.SENT.value


class TestCancelAndActions:
    @pytest.mark.parametrize("status", [BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED, BroadcastStatus.SENDING])
    async def test_an_unfinished_broadcast_cancels(self, status):
        row = _row(status)
        await _service(row).cancel("b-1", "admin-1")
        assert row.status == BroadcastStatus.CANCELLED.value

    async def test_a_sent_broadcast_cannot_be_cancelled(self):
        with pytest.raises(InvalidResourceStateException):
            await _service(_row(BroadcastStatus.SENT)).cancel("b-1", "admin-1")

    @pytest.mark.parametrize("status, actions", [
        (BroadcastStatus.DRAFT, [BroadcastAction.SEND, BroadcastAction.CANCEL]),
        (BroadcastStatus.SCHEDULED, [BroadcastAction.SEND, BroadcastAction.CANCEL]),
        (BroadcastStatus.SENDING, [BroadcastAction.CANCEL]),
        (BroadcastStatus.SENT, []),
        (BroadcastStatus.CANCELLED, []),
    ])
    def test_the_backend_says_which_actions_a_status_allows(self, status, actions):
        assert allowed_actions(status) == actions
