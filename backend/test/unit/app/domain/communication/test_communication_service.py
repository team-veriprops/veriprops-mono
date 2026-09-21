"""CommunicationService (§11.1): the authorization gates — agent-on-verification,
read-only-when-approved, and the customer-thread ownership delegation."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.state.status import TaskState
from main.app.domain.communication.chat_message.models import MessageKind, SenderKind
from main.app.domain.communication.conversation.models import (
    ConversationChannel,
    ConversationType,
)
from main.app.domain.communication.service import CommunicationService
from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.communication.conversation_participant.models import ConversationParticipant
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidResourceStateException,
    ResourceNotFoundException,
)


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


def _service(tasks, user_type="USER"):
    svc = object.__new__(CommunicationService)
    svc._conversations = MagicMock()
    svc._participants = MagicMock()
    svc._chat = MagicMock()
    svc._verifications = MagicMock()
    svc._tasks = MagicMock()
    svc._tasks.list_for_verification = AsyncMock(return_value=list(tasks))
    svc._users = MagicMock()
    svc._users.get_model = AsyncMock(return_value=SimpleNamespace(user_type=user_type))
    # No visibility window unless a test says otherwise — web threads never have one.
    svc._participants.get_membership = AsyncMock(return_value=None)
    return svc


def _task(task_id, agent_id, state=TaskState.IN_PROGRESS):
    return SimpleNamespace(
        id=task_id, assigned_agent_id=agent_id, state=state.value, deleted=False
    )


async def test_agent_not_assigned_cannot_open_thread():
    svc = _service(tasks=[_task("t1", "other-agent")])
    with pytest.raises(ForbiddenException):
        await svc._assert_agent_on_verification("v-1", "agent-1")


async def test_agent_assigned_passes():
    svc = _service(tasks=[_task("t1", "agent-1")])
    await svc._assert_agent_on_verification("v-1", "agent-1")  # no raise


async def test_approved_task_thread_is_read_only_for_agent():
    svc = _service(tasks=[])
    svc._tasks.get_model = AsyncMock(
        return_value=_task("t1", "agent-1", state=TaskState.APPROVED)
    )
    with pytest.raises(ForbiddenException):
        await svc._assert_task_writable("t1", "agent-1")


async def test_admin_sees_shared_inbox_and_counter():
    """G4: an admin's conversation list + counter cover every verification thread, not just
    ones they've personally joined."""
    svc = _service(tasks=[], user_type="ADMIN")
    svc._conversations.list_for_admin = AsyncMock(return_value=["all-threads"])
    svc._conversations.unread_count_for_admin = AsyncMock(return_value=3)
    svc._conversations.list_for_user = AsyncMock(return_value=[])
    svc._participants.unread_conversation_count = AsyncMock(return_value=0)

    convos = await svc.list_conversations("admin-1")
    count = await svc.unread_count("admin-1")

    assert convos == ["all-threads"]
    assert count == 3
    svc._conversations.list_for_admin.assert_awaited_with("admin-1")
    svc._conversations.list_for_user.assert_not_called()


async def test_non_admin_uses_participant_inbox():
    svc = _service(tasks=[], user_type="USER")
    svc._conversations.list_for_admin = AsyncMock(return_value=["all"])
    svc._participants.unread_conversation_count = AsyncMock(return_value=1)

    count = await svc.unread_count("cust-1")

    assert count == 1
    svc._conversations.list_for_admin.assert_not_called()


async def test_customer_send_delegates_through_ownership_gate():
    svc = _service(tasks=[])
    svc._verifications.get_owned = AsyncMock(return_value=SimpleNamespace(id="v-1"))
    convo = SimpleNamespace(id="conv-1", type=ConversationType.CUSTOMER_ADMIN.value)
    svc._conversations.get_or_create_verification_thread = AsyncMock(return_value=convo)
    svc._participants.ensure_participant = AsyncMock()
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.customer_send("v-1", "cust-1", "hello there")

    svc._verifications.get_owned.assert_awaited_with("v-1", "cust-1")
    args, kwargs = svc._chat.send.call_args
    assert args[2] == SenderKind.CUSTOMER


def _customer_thread_ready(svc):
    svc._verifications.get_owned = AsyncMock(return_value=SimpleNamespace(id="v-1"))
    svc._conversations.get_or_create_verification_thread = AsyncMock(
        return_value=SimpleNamespace(id="conv-1", type=ConversationType.CUSTOMER_ADMIN.value)
    )
    svc._participants.ensure_participant = AsyncMock()
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))


async def test_a_customers_message_is_always_plain_chat():
    """The kind is server-owned. `SYSTEM_AUTO` exempts platform copy from the fraud scan, so
    a kind taken from the wire let a customer post a phone number or bank details unscanned."""
    svc = _service(tasks=[])
    _customer_thread_ready(svc)

    await svc.customer_send("v-1", "cust-1", "call me on 0801...")

    assert svc._chat.send.call_args.kwargs["kind"] == MessageKind.CHAT


# ── sender_kind is derived server-side, never trusted from the client (H2) ──────

def _expect_thread(svc, convo):
    """Stub whichever fetch the caller's role will take.

    Admins go through the ungated shared-inbox fetch and everyone else through the
    membership check, so a test that stubbed only one silently exercised neither.
    """
    svc._conversations.get_owned_participant = AsyncMock(return_value=convo)
    svc._conversations.get_for_admin = AsyncMock(return_value=convo)


def _convo(convo_type, channel=ConversationChannel.WEB, external_ref=None):
    # `type`/`channel` are what the D57 hand-over check reads: a person replying on any
    # thread the assistant answers takes it off the assistant; a staff thread has none.
    return SimpleNamespace(
        id="conv-1",
        type=convo_type.value,
        deleted=False,
        channel=channel.value,
        external_ref=external_ref,
    )


async def test_post_message_customer_cannot_spoof_admin_or_system():
    """A non-admin member of a customer↔admin thread always posts as CUSTOMER — there is
    no client-supplied sender_kind path to impersonate ADMIN/SYSTEM."""
    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_owned_participant = AsyncMock(
        return_value=_convo(ConversationType.CUSTOMER_ADMIN)
    )
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.post_message("conv-1", "cust-1", "hello")

    assert svc._chat.send.call_args.args[2] == SenderKind.CUSTOMER


async def test_post_message_admin_derives_admin_kind():
    svc = _service(tasks=[], user_type="ADMIN")
    _expect_thread(svc, _convo(ConversationType.CUSTOMER_ADMIN))
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.post_message("conv-1", "admin-1", "hello")

    assert svc._chat.send.call_args.args[2] == SenderKind.ADMIN


async def test_post_message_agent_thread_derives_agent_kind():
    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_owned_participant = AsyncMock(
        return_value=_convo(ConversationType.ADMIN_AGENT)
    )
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.post_message("conv-1", "agent-1", "on my way")

    assert svc._chat.send.call_args.args[2] == SenderKind.AGENT


@pytest.mark.parametrize("user_type", ["USER", "ADMIN"])
async def test_the_generic_send_path_always_sends_plain_chat(user_type):
    """The generic send path accepted any `kind` too — including from admins, whose own
    messages are scanned like everyone else's."""
    svc = _service(tasks=[], user_type=user_type)
    _expect_thread(svc, _convo(ConversationType.CUSTOMER_ADMIN))
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.post_message("conv-1", "someone-1", "text me on 0801...")

    assert svc._chat.send.call_args.kwargs["kind"] == MessageKind.CHAT


# ── The visibility window (§26.8, §26.4.4) ─────────────────────────

async def test_a_released_whatsapp_thread_refuses_the_former_owners_message():
    """After unlinking, the customer keeps their history but cannot write into a thread
    that now belongs to nobody — and the refusal is never a 403, which the web client
    turns into a /forbidden redirect."""
    from datetime import datetime, timezone

    svc = _service(tasks=[], user_type="USER")
    _expect_thread(svc, _convo(ConversationType.GENERAL_SUPPORT, channel=ConversationChannel.WHATSAPP))
    svc._participants.get_membership = AsyncMock(return_value=ConversationParticipant(
        visible_from=datetime(2026, 9, 16, tzinfo=timezone.utc),
        visible_until=datetime(2026, 9, 17, tzinfo=timezone.utc),
    ))
    svc._chat.send = AsyncMock()

    with pytest.raises(InvalidResourceStateException):
        await svc.post_message("conv-1", "cust-1", "hello again")

    svc._chat.send.assert_not_awaited()


async def test_a_member_reads_only_inside_their_window():
    from datetime import datetime, timezone

    linked = datetime(2026, 9, 16, tzinfo=timezone.utc)
    svc = _service(tasks=[], user_type="USER")
    _expect_thread(svc, _convo(ConversationType.GENERAL_SUPPORT, channel=ConversationChannel.WHATSAPP))
    svc._participants.get_membership = AsyncMock(
        return_value=ConversationParticipant(visible_from=linked)
    )
    svc._chat.list_messages = AsyncMock(return_value="page")

    await svc.list_messages("conv-1", "cust-1", 0, 30)

    kwargs = svc._chat.list_messages.await_args.kwargs
    assert kwargs["visible_from"] == linked
    assert kwargs["visible_until"] is None


async def test_an_admin_reads_the_whole_thread():
    svc = _service(tasks=[], user_type="ADMIN")
    svc._chat.list_messages = AsyncMock(return_value="page")

    await svc.list_messages("conv-1", "admin-1", 0, 30)

    kwargs = svc._chat.list_messages.await_args.kwargs
    assert kwargs["visible_from"] is None and kwargs["visible_until"] is None
    # The console sees delivery ticks; members see "seen by support" instead.
    assert kwargs["viewer_is_admin"] is True
    svc._participants.get_membership.assert_not_awaited()


# ── D57: a human reply silences the bot ───────────────────────────

def _stub_take_over(monkeypatch) -> AsyncMock:
    """Replace `take_over` on the class rather than the container entry.

    Kink resolves an `@inject` class through a registered factory, so swapping an entry
    in the service registry is quietly ignored and the real service runs. Patching the
    method covers whatever instance the container decides to build, and monkeypatch
    restores it — a leaked fake would silently disarm D57 for the rest of the run.
    """
    from main.app.domain.communication.assistant.session.service import (
        AssistantSessionService,
    )

    take_over = AsyncMock()
    monkeypatch.setattr(AssistantSessionService, "take_over", take_over)
    return take_over


@pytest.mark.parametrize(
    "convo",
    [
        _convo(
            ConversationType.GENERAL_SUPPORT,
            channel=ConversationChannel.WHATSAPP,
            external_ref="+2348012345678",
        ),
        _convo(ConversationType.GENERAL_SUPPORT),
        _convo(ConversationType.CUSTOMER_ADMIN),
    ],
    ids=["whatsapp", "web-support", "case-customer-thread"],
)
async def test_an_admin_reply_takes_any_assistant_thread_off_the_assistant(monkeypatch, convo):
    """The other half of the sticky-HUMAN rule, on every thread the assistant answers (D93).
    Without it the assistant would keep answering over an agent mid-conversation, which is
    the failure customers notice most."""
    svc = _service(tasks=[], user_type="ADMIN")
    _expect_thread(svc, convo)
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))
    take_over = _stub_take_over(monkeypatch)

    await svc.post_message("conv-1", "admin-1", "Hi, I'll take it from here.")

    take_over.assert_awaited_once_with(convo)


async def test_a_staff_thread_never_touches_an_assistant_session(monkeypatch):
    """Admin and agent talking to each other is never an assistant thread."""
    svc = _service(tasks=[], user_type="ADMIN")
    _expect_thread(svc, _convo(ConversationType.ADMIN_AGENT))
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))
    take_over = _stub_take_over(monkeypatch)

    await svc.post_message("conv-1", "admin-1", "hello")

    take_over.assert_not_awaited()


async def test_a_customers_own_message_does_not_silence_the_assistant(monkeypatch):
    """A customer writing on their own WhatsApp thread is the assistant's whole job — only a
    *human agent* speaking takes the thread over."""
    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_owned_participant = AsyncMock(
        return_value=_convo(
            ConversationType.GENERAL_SUPPORT,
            channel=ConversationChannel.WHATSAPP,
            external_ref="+2348012345678",
        )
    )
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))
    take_over = _stub_take_over(monkeypatch)

    await svc.post_message("conv-1", "cust-1", "any update?")

    take_over.assert_not_awaited()


# ── Admins are a shared inbox for writing too (§N.3, G4) ─────────

async def test_an_admin_can_reply_to_a_thread_they_never_joined():
    """The gap the WhatsApp console found: admins work threads they are not participants
    of, so requiring membership left a §26.8 enquiry readable and unanswerable — and D57's
    bot take-over, which fires on an agent's reply, could never happen."""
    svc = _service(tasks=[], user_type="ADMIN")
    svc._conversations.get_owned_participant = AsyncMock(
        side_effect=AssertionError("an admin must not be gated on membership")
    )
    svc._conversations.get_for_admin = AsyncMock(
        return_value=_convo(ConversationType.GENERAL_SUPPORT)
    )
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.post_message("conv-1", "admin-1", "Hi, I'll take this one.")

    svc._conversations.get_for_admin.assert_awaited_once_with("conv-1")
    assert svc._chat.send.call_args.args[2] == SenderKind.ADMIN


async def test_a_non_admin_is_still_gated_on_membership():
    """The shared inbox is an admin privilege, not a hole: a customer must still be a
    participant, or a thread id becomes a way to read someone else's conversation."""
    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_owned_participant = AsyncMock(
        side_effect=ResourceNotFoundException(resource="Conversation")
    )
    svc._conversations.get_for_admin = AsyncMock(
        side_effect=AssertionError("a non-admin must never reach the ungated fetch")
    )

    with pytest.raises(ResourceNotFoundException):
        await svc.post_message("conv-1", "cust-1", "let me in")


async def test_the_admin_inbox_is_passed_through_with_its_filter_and_search():
    from main.app.domain.communication.conversation.models import AdminInboxFilter

    svc = _service(tasks=[], user_type="ADMIN")
    svc._conversations.list_admin_inbox = AsyncMock(return_value="page")

    result = await svc.admin_inbox("admin-1", 0, 10, inbox_filter=AdminInboxFilter.WHATSAPP, query="+234")

    assert result == "page"
    svc._conversations.list_admin_inbox.assert_awaited_once_with(
        "admin-1", 0, 10, inbox_filter=AdminInboxFilter.WHATSAPP, query="+234"
    )


# ── A queued reply read in the portal stays off the phone (D92) ─────

class TestReadingInThePortalCancelsQueuedPhoneDelivery:
    @staticmethod
    def _member_reads(user_type="USER", channel=ConversationChannel.WHATSAPP, membership=None):
        from datetime import datetime, timezone

        svc = _service(tasks=[], user_type=user_type)
        svc._conversations.get_owned_participant = AsyncMock(
            return_value=_convo(ConversationType.GENERAL_SUPPORT, channel=channel)
        )
        svc._conversations.get_for_admin = AsyncMock(
            return_value=_convo(ConversationType.GENERAL_SUPPORT, channel=channel)
        )
        svc._participants.mark_read = AsyncMock()
        svc._participants.get_membership = AsyncMock(return_value=membership or ConversationParticipant(
            visible_from=datetime(2026, 9, 16, tzinfo=timezone.utc),
        ))
        svc._chat.cancel_pending_channel_delivery = AsyncMock(return_value=1)
        return svc

    async def test_the_customer_reading_their_whatsapp_thread_cancels_it(self):
        from datetime import datetime, timezone

        svc = self._member_reads()

        await svc.mark_read("conv-1", "cust-1")

        svc._chat.cancel_pending_channel_delivery.assert_awaited_once()
        kwargs = svc._chat.cancel_pending_channel_delivery.await_args.kwargs
        assert kwargs["visible_from"] == datetime(2026, 9, 16, tzinfo=timezone.utc)
        assert kwargs["read_at"] is not None

    async def test_an_admin_opening_the_thread_is_not_the_customer_reading_it(self):
        svc = self._member_reads(user_type="ADMIN")

        await svc.mark_read("conv-1", "admin-1")

        svc._chat.cancel_pending_channel_delivery.assert_not_awaited()

    async def test_a_web_thread_has_nothing_queued_for_a_phone(self):
        svc = self._member_reads(channel=ConversationChannel.WEB)

        await svc.mark_read("conv-1", "cust-1")

        svc._chat.cancel_pending_channel_delivery.assert_not_awaited()

    async def test_a_former_owner_reading_history_does_not_cancel_the_new_owners_replies(self):
        from datetime import datetime, timezone

        released = ConversationParticipant(
            visible_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
            visible_until=datetime(2026, 9, 10, tzinfo=timezone.utc),
        )
        svc = self._member_reads(membership=released)

        await svc.mark_read("conv-1", "cust-1")

        svc._chat.cancel_pending_channel_delivery.assert_not_awaited()



# ── The assistant on web threads (§16.7, D93) ─────────────────────

async def test_the_assistant_can_never_fail_a_customers_send(monkeypatch):
    """The customer's message is already in the thread; an assistant fault must not turn a
    successful send into an error."""
    from kink import di

    from main.app.domain.communication.assistant.web import WebAssistantService

    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_for_admin = AsyncMock(return_value=_convo(ConversationType.GENERAL_SUPPORT))
    broken = MagicMock(after_customer_message=AsyncMock(side_effect=RuntimeError("model down")))
    monkeypatch.setitem(di._services, WebAssistantService, broken)
    monkeypatch.setattr(WebAssistantService, "after_customer_message", broken.after_customer_message)

    outcome = await svc.answer_with_assistant(SimpleNamespace(id="msg-1", conversation_id="conv-1"))

    assert outcome.reply is None and outcome.pending is False


async def test_a_turn_request_is_gated_on_membership(monkeypatch):
    from main.app.domain.communication.assistant.web import WebAssistantService

    svc = _service(tasks=[], user_type="USER")
    svc._conversations.get_owned_participant = AsyncMock(
        side_effect=ResourceNotFoundException(resource="Conversation")
    )
    run = AsyncMock()
    monkeypatch.setattr(WebAssistantService, "run_pending_turn", run)

    with pytest.raises(ResourceNotFoundException):
        await svc.run_assistant_turn("conv-1", "stranger")

    run.assert_not_awaited()
