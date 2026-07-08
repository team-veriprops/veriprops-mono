"""CommunicationService (§11.1): the authorization gates — agent-on-verification,
read-only-when-approved, and the customer-thread ownership delegation."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.state.status import TaskState
from main.app.domain.communication.chat_message.models import SenderKind
from main.app.domain.communication.conversation.models import ConversationType
from main.app.domain.communication.service import CommunicationService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ForbiddenException


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
    convo = SimpleNamespace(id="conv-1")
    svc._conversations.get_or_create_verification_thread = AsyncMock(return_value=convo)
    svc._participants.ensure_participant = AsyncMock()
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(id="msg-1"))

    await svc.customer_send("v-1", "cust-1", "hello there")

    svc._verifications.get_owned.assert_awaited_with("v-1", "cust-1")
    args, kwargs = svc._chat.send.call_args
    assert args[2] == SenderKind.CUSTOMER


# ── sender_kind is derived server-side, never trusted from the client (H2) ──────

def _convo(convo_type):
    return SimpleNamespace(id="conv-1", type=convo_type.value, deleted=False)


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
    svc._conversations.get_owned_participant = AsyncMock(
        return_value=_convo(ConversationType.CUSTOMER_ADMIN)
    )
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
