"""ChatMessageService (§11.2, §4.7): the send fast-lane vs hold, admin approve/reject
journey, the customer-safe sender projection (§11.3), and the clarification flow. Deps
mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.chat_message.models import MessageKind, SenderKind
from main.app.domain.communication.chat_message.service import HELD_NOTICE, ChatMessageService
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
    session.add = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _service():
    svc = object.__new__(ChatMessageService)
    svc._chat_message_repo = MagicMock()
    svc._conversations = MagicMock()
    svc._participants = MagicMock()
    svc._users = MagicMock()
    svc._audit = MagicMock()

    # create_return_model echoes a stored row from the create DTO.
    async def _create(dto):
        return SimpleNamespace(
            id="msg-1",
            conversation_id=dto.conversation_id,
            sender_user_id=dto.sender_user_id,
            sender_kind=dto.sender_kind.value,
            body=dto.body,
            task_id=dto.task_id,
            state=dto.state.value,
            message_kind=dto.message_kind.value,
            clarification_status=dto.clarification_status.value if dto.clarification_status else None,
            flagged_categories=dto.flagged_categories,
            delivered_at=dto.delivered_at,
            held_at=dto.held_at,
            reviewed_by=None,
            reviewed_at=None,
            date_created=Utils.datetime_now(),
            deleted=False,
        )

    svc._chat_message_repo.create_return_model = AsyncMock(side_effect=_create)
    svc._participants.ensure_participant = AsyncMock()
    svc._participants._participant_repo = MagicMock()
    svc._participants._participant_repo.list_for_conversation = AsyncMock(return_value=[])
    svc._conversations.touch = AsyncMock()
    svc._conversations._conversation_repo = MagicMock()
    svc._audit.schedule = MagicMock()
    return svc


def _conversation():
    return SimpleNamespace(id="conv-1", type="CUSTOMER_ADMIN", verification_id="v-1")


async def test_clean_message_delivers_immediately():
    svc = _service()
    msg = await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, "Please confirm the plot")
    assert msg.state == ChatMessageState.DELIVERED.value
    assert msg.delivered_at is not None
    svc._conversations.touch.assert_awaited()  # delivery bumps the thread


async def test_flagged_message_is_held():
    svc = _service()
    msg = await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, "call me on 08031234567")
    assert msg.state == ChatMessageState.HELD.value
    assert msg.held_at is not None
    assert msg.delivered_at is None
    # A held message does not bump the thread (nothing delivered).
    svc._conversations.touch.assert_not_awaited()


async def test_blank_and_oversize_bodies_rejected():
    from main.appodus_utils.exception.exceptions import ValidationException

    svc = _service()
    with pytest.raises(ValidationException):
        await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, "   ")
    with pytest.raises(ValidationException):
        await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, "x" * 2001)


async def test_approve_held_message_delivers():
    svc = _service()
    held = SimpleNamespace(
        id="msg-1", conversation_id="conv-1", sender_user_id="cust-1",
        state=ChatMessageState.HELD.value, delivered_at=None, deleted=False,
    )
    svc._chat_message_repo.get_model = AsyncMock(return_value=held)
    svc._conversations._conversation_repo.get_model = AsyncMock(return_value=_conversation())

    result = await svc.approve("msg-1", "admin-1")
    assert result.state == ChatMessageState.DELIVERED.value
    assert result.reviewed_by == "admin-1"


async def test_reject_held_message_blocks():
    svc = _service()
    held = SimpleNamespace(
        id="msg-1", conversation_id="conv-1", sender_user_id="cust-1",
        state=ChatMessageState.HELD.value, deleted=False,
    )
    svc._chat_message_repo.get_model = AsyncMock(return_value=held)

    result = await svc.reject("msg-1", "admin-1")
    assert result.state == ChatMessageState.BLOCKED.value


async def test_cannot_review_a_non_held_message():
    from main.appodus_utils.exception.exceptions import ForbiddenException

    svc = _service()
    delivered = SimpleNamespace(
        id="msg-1", state=ChatMessageState.DELIVERED.value, deleted=False,
    )
    svc._chat_message_repo.get_model = AsyncMock(return_value=delivered)
    with pytest.raises(ForbiddenException):
        await svc.approve("msg-1", "admin-1")


async def test_agent_sender_projection_is_first_name_only():
    """§11.3 exit: a customer-facing sender never carries last name, email, or phone."""
    svc = _service()
    svc._users.get_model = AsyncMock(return_value=SimpleNamespace(
        first_name="Ada", avatar_url="http://x/a.png",
        last_name="Okoro", email="ada@example.com", phone="+2348000000000",
    ))
    message = SimpleNamespace(sender_kind=SenderKind.AGENT.value, sender_user_id="agent-1")
    sender = await svc._sender_dto(message)

    dumped = sender.model_dump()
    assert sender.first_name == "Ada"
    assert "Okoro" not in str(dumped)
    assert "ada@example.com" not in str(dumped)
    assert "2348000000000" not in str(dumped)


async def test_clarification_request_carries_open_status():
    svc = _service()
    msg = await svc.send(
        _conversation(), "cust-1", SenderKind.CUSTOMER, "What time can we access the site?",
        kind=MessageKind.CLARIFICATION_REQUEST,
    )
    assert msg.message_kind == MessageKind.CLARIFICATION_REQUEST.value
    assert msg.clarification_status == "OPEN"
