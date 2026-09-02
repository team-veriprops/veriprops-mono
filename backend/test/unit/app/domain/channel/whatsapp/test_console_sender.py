"""WhatsAppConsoleSender — the outbound half of Decision K (PRD §7.3.3, §7.7, WA-12/WA-41).

The defect this module exists to close: an agent's reply was written into the WhatsApp
thread and never sent anywhere. These tests pin the four properties that make the fix
trustworthy rather than merely present.

* Inside Meta's window the agent's **own words** go out.
* Outside it they are **queued, not dropped** — the customer gets the `window_reopen`
  nudge and the words follow when they answer. Dropping them would leave a customer with
  a nudge and then silence, because the thread is sticky-`HUMAN` by then (D57).
* **One nudge per episode**, however many messages the agent types.
* Nothing else on the thread is re-sent: a bot reply already went out through
  `bot/sender.py`, and sending it again answers the customer twice.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.console_sender import (
    ANONYMOUS_FIRST_NAME,
    WhatsAppConsoleSender,
)
from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.chat_message.models import SenderKind
from main.app.domain.communication.conversation.models import ConversationChannel
from main.appodus_utils.db.session import db_session_ctx

PHONE = "+2348012345678"


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
def outbound_enabled(monkeypatch):
    """The sender declines to dispatch when outbound messaging is off, which is the right
    local-dev posture but would make every delivery assertion here vacuous."""
    from main.app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ENABLE_OUT_MESSAGING", True)


@pytest.fixture
def window_reopen(monkeypatch):
    """Capture `window_reopen` sends without reaching the messaging pipeline."""
    from kink import di
    from main.app.domain.user.user_messages import AccountSecurityMessages

    sender = MagicMock()
    sender.send_whatsapp_window_reopen_message = AsyncMock()
    monkeypatch.setitem(di._services, AccountSecurityMessages, sender)
    return sender.send_whatsapp_window_reopen_message


def _conversation(channel=ConversationChannel.WHATSAPP, external_ref=PHONE):
    return SimpleNamespace(
        id="conv-1", channel=channel.value, external_ref=external_ref, verification_id=None
    )


def _message(
    body="On it — I'll check and come back to you.",
    sender_kind=SenderKind.ADMIN,
    channel_delivered_at=None,
    message_id="msg-1",
):
    return SimpleNamespace(
        id=message_id,
        body=body,
        sender_kind=sender_kind.value,
        state=ChatMessageState.DELIVERED.value,
        channel_delivered_at=channel_delivered_at,
    )


def _sender(*, window_open: bool, queued=(), user_id=None, first_name=None):
    svc = object.__new__(WhatsAppConsoleSender)
    svc._messaging_service = MagicMock(send_message=AsyncMock())
    svc._whatsapp_window_service = MagicMock(is_open=AsyncMock(return_value=window_open))
    svc._whatsapp_link_service = MagicMock(
        resolve_user_for_phone=AsyncMock(return_value=user_id)
    )
    svc._chat_message_repo = MagicMock(
        list_pending_channel_delivery=AsyncMock(return_value=list(queued)),
        _session=MagicMock(),
    )
    svc._user_repo = MagicMock(
        get_model=AsyncMock(
            return_value=SimpleNamespace(first_name=first_name) if first_name else None
        )
    )
    return svc


def _sent_texts(svc) -> list[str]:
    return [
        call.args[0].payload.text
        for call in svc._messaging_service.send_message.await_args_list
    ]


class TestInsideTheWindow:
    async def test_the_agents_own_words_reach_the_customer(self):
        svc = _sender(window_open=True)
        message = _message()

        await svc.deliver(_conversation(), message)

        assert _sent_texts(svc) == ["On it — I'll check and come back to you."]

    async def test_a_delivered_reply_is_stamped_so_it_never_goes_twice(self):
        svc = _sender(window_open=True)
        message = _message()

        await svc.deliver(_conversation(), message)

        assert message.channel_delivered_at is not None

    async def test_a_transport_failure_leaves_the_message_queued_rather_than_raising(self):
        # The reply is already in the thread and the agent has been told it sent. Raising
        # would report a failure to the half of the system that succeeded; leaving it
        # unstamped means the next inbound retries it.
        svc = _sender(window_open=True)
        svc._messaging_service.send_message = AsyncMock(side_effect=RuntimeError("meta down"))
        message = _message()

        await svc.deliver(_conversation(), message)

        assert message.channel_delivered_at is None


class TestOutsideTheWindow:
    async def test_the_nudge_template_goes_instead_of_the_reply(self, window_reopen):
        svc = _sender(window_open=False)
        message = _message()

        await svc.deliver(_conversation(), message)

        # Meta will not deliver free text this late, so nothing free-text left.
        assert _sent_texts(svc) == []
        window_reopen.assert_awaited_once()

    async def test_the_reply_is_queued_not_dropped(self, window_reopen):
        svc = _sender(window_open=False)
        message = _message()

        await svc.deliver(_conversation(), message)

        # Null `channel_delivered_at` is the queue: `ingest` flushes it when the customer
        # answers and reopens the window.
        assert message.channel_delivered_at is None

    async def test_a_second_reply_joins_the_queue_without_a_second_nudge(self, window_reopen):
        # Three templates for three messages would read as spam and cost three template
        # sends to say one thing.
        already_queued = _message(message_id="msg-earlier")
        svc = _sender(window_open=False, queued=[already_queued, _message()])

        await svc.deliver(_conversation(), _message())

        window_reopen.assert_not_awaited()

    async def test_an_unlinked_number_is_greeted_neutrally(self, window_reopen):
        # A §7.8 enquiry thread usually has no account behind it yet, and the template
        # still has to render — a blank or a raw phone number reads as broken.
        svc = _sender(window_open=False, user_id=None)

        await svc.deliver(_conversation(), _message())

        context = window_reopen.await_args.kwargs["context"]
        assert ANONYMOUS_FIRST_NAME in context.values()

    async def test_a_linked_customer_is_greeted_by_name(self, window_reopen):
        svc = _sender(window_open=False, user_id="user-1", first_name="Ada")

        await svc.deliver(_conversation(), _message())

        context = window_reopen.await_args.kwargs["context"]
        assert "Ada" in context.values()


class TestWhatNeverGoesOut:
    async def test_a_bot_reply_is_not_re_sent(self):
        # `bot/sender.py` already delivered it; sending again answers the customer twice.
        svc = _sender(window_open=True)

        await svc.deliver(_conversation(), _message(sender_kind=SenderKind.SYSTEM))

        assert _sent_texts(svc) == []

    async def test_a_customers_own_message_is_not_echoed_back(self):
        svc = _sender(window_open=True)

        await svc.deliver(_conversation(), _message(sender_kind=SenderKind.CUSTOMER))

        assert _sent_texts(svc) == []

    async def test_a_website_thread_has_no_channel_to_send_on(self):
        svc = _sender(window_open=True)

        await svc.deliver(_conversation(channel=ConversationChannel.WEB), _message())

        assert _sent_texts(svc) == []

    async def test_a_whatsapp_thread_with_no_number_is_a_data_fault_not_a_target(self):
        svc = _sender(window_open=True)

        await svc.deliver(_conversation(external_ref=None), _message())

        assert _sent_texts(svc) == []

    async def test_an_already_delivered_message_is_not_sent_again(self):
        # `_deliver_effects` runs on both send and approve; a re-entry must not duplicate
        # the message on the customer's phone.
        from main.appodus_utils import Utils

        svc = _sender(window_open=True)

        await svc.deliver(_conversation(), _message(channel_delivered_at=Utils.datetime_now()))

        assert _sent_texts(svc) == []


class TestFlush:
    async def test_queued_replies_go_out_oldest_first(self):
        first = _message(body="Checking now.", message_id="m1")
        second = _message(body="Found it — survey is with the office.", message_id="m2")
        svc = _sender(window_open=True, queued=[first, second])

        await svc.flush(_conversation())

        # The agent wrote them as a sequence; delivering out of order rewrites the
        # conversation the console shows.
        assert _sent_texts(svc) == [
            "Checking now.",
            "Found it — survey is with the office.",
        ]
        assert first.channel_delivered_at is not None
        assert second.channel_delivered_at is not None

    async def test_an_empty_queue_sends_nothing(self):
        svc = _sender(window_open=True, queued=[])

        await svc.flush(_conversation())

        assert _sent_texts(svc) == []
