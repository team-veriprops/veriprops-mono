"""ChatMessageService (§11.2, §4.7): the send fast-lane vs hold, admin approve/reject
journey, the customer-safe sender projection (§11.3), and the clarification flow. Deps
mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.core.state.status import ChatMessageState
from main.app.domain.communication.chat_message.models import (
    MessageKind,
    MessageSource,
    SenderKind,
)
from main.app.domain.communication.chat_message.service import ChatMessageService
from main.app.domain.communication.conversation.models import ConversationChannel
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
            source=dto.source.value,
            external_message_id=dto.external_message_id,
            body=dto.body,
            task_id=dto.task_id,
            state=dto.state.value,
            message_kind=dto.message_kind.value,
            clarification_status=dto.clarification_status.value if dto.clarification_status else None,
            flagged_categories=dto.flagged_categories,
            media_kind=dto.media_kind.value if dto.media_kind else None,
            delivered_at=dto.delivered_at,
            channel_delivered_at=None,
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


def _conversation(channel=ConversationChannel.WEB, external_ref=None):
    # `channel` is what decides whether delivery also has to leave over a transport (§26.7);
    # a web thread has none, which is the default here.
    return SimpleNamespace(
        id="conv-1", type="CUSTOMER_ADMIN", verification_id="v-1",
        channel=channel.value, external_ref=external_ref,
    )


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


# ── Source labeling + the platform-authored scan exemption (§26.3.3, §26.6) ──


async def test_whatsapp_text_runs_the_same_fraud_scan_as_web_chat():
    # WA-13: a WhatsApp message is held on exactly the same signals — the channel
    # changes where it came from, never how it is policed.
    svc = _service()
    msg = await svc.send(
        _conversation(), "cust-1", SenderKind.CUSTOMER, "call me on 08031234567",
        source=MessageSource.WHATSAPP,
    )
    assert msg.state == ChatMessageState.HELD.value
    assert msg.source == MessageSource.WHATSAPP.value


async def test_whatsapp_message_records_its_channel_native_id():
    svc = _service()
    msg = await svc.send(
        _conversation(), "cust-1", SenderKind.CUSTOMER, "Hello",
        source=MessageSource.WHATSAPP, external_message_id="wamid.A1",
    )
    assert msg.external_message_id == "wamid.A1"


async def test_messages_default_to_the_web_surface():
    svc = _service()
    msg = await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, "Hello")
    assert msg.source == MessageSource.WEB.value


async def test_platform_authored_copy_is_never_held():
    # Bot replies and status auto-posts carry veriprops.ng links and the official
    # WhatsApp number by design (the payment pledge, §26.1.1). Scanning them would hold
    # the very messages that keep a customer oriented.
    svc = _service()
    pledge = "Payments only ever happen at veriprops.ng — check the address bar before you pay."
    msg = await svc.send(
        _conversation(), None, SenderKind.SYSTEM, pledge, kind=MessageKind.SYSTEM_AUTO
    )
    assert msg.state == ChatMessageState.DELIVERED.value
    assert msg.flagged_categories is None


async def test_a_human_message_with_the_same_text_is_still_scanned():
    # The exemption is about who authored the copy, not about the words in it.
    svc = _service()
    pledge = "Payments only ever happen at veriprops.ng — check the address bar before you pay."
    msg = await svc.send(_conversation(), "cust-1", SenderKind.CUSTOMER, pledge)
    assert msg.state == ChatMessageState.HELD.value


async def test_a_brand_new_thread_is_bumped_by_its_first_message():
    """A thread opened by the same request that posts into it must still be bumped.

    `touch` used to re-fetch the conversation by id; for a WhatsApp enquiry from an
    unknown number the thread is created in that same uncommitted transaction, so the
    fetch returned None, the bump was skipped, and the thread never appeared in the
    admin inbox (which orders on `last_message_at`).
    """
    svc = _service()
    convo = _conversation()
    await svc.send(convo, "cust-1", SenderKind.CUSTOMER, "Hello")

    touched, at = svc._conversations.touch.await_args.args
    assert touched is convo, "touch must receive the live object, not an id to re-fetch"
    assert at is not None


class TestChannelDelivery:
    """§26.7/WA-12 — a reply on a WhatsApp thread has to leave the building.

    `_deliver_effects` is the seam, and that choice is the substance of these tests: it is
    the *one* place both a clean send and an approved-after-hold release pass through, so
    a held reply cannot reach a customer's phone before an admin has cleared it without
    that needing a guard of its own.
    """

    @staticmethod
    def _console_sender(monkeypatch):
        from kink import di
        from main.app.domain.channel.whatsapp.console_sender import WhatsAppConsoleSender

        sender = MagicMock(deliver=AsyncMock())
        monkeypatch.setitem(di._services, WhatsAppConsoleSender, sender)
        return sender

    async def test_a_clean_reply_on_a_whatsapp_thread_is_carried_out(self, monkeypatch):
        sender = self._console_sender(monkeypatch)
        svc = _service()
        convo = _conversation(ConversationChannel.WHATSAPP, "+2348012345678")

        await svc.send(convo, "admin-1", SenderKind.ADMIN, "On it — checking now.")

        sender.deliver.assert_awaited_once()

    async def test_a_web_thread_never_reaches_the_channel_adapter(self, monkeypatch):
        sender = self._console_sender(monkeypatch)
        svc = _service()

        await svc.send(_conversation(), "admin-1", SenderKind.ADMIN, "On it.")

        sender.deliver.assert_not_awaited()

    async def test_a_held_reply_is_not_delivered_until_it_is_approved(self, monkeypatch):
        # The whole reason the hook lives in `_deliver_effects`: a message the fraud scan
        # caught must not reach the customer's phone while it is still under review.
        sender = self._console_sender(monkeypatch)
        svc = _service()
        convo = _conversation(ConversationChannel.WHATSAPP, "+2348012345678")

        msg = await svc.send(
            convo, "admin-1", SenderKind.ADMIN, "just call me on 08031234567 instead"
        )

        assert msg.state == ChatMessageState.HELD.value
        sender.deliver.assert_not_awaited()

    async def test_approving_a_held_reply_releases_it_to_the_channel(self, monkeypatch):
        sender = self._console_sender(monkeypatch)
        svc = _service()
        held = SimpleNamespace(
            id="msg-1", conversation_id="conv-1", sender_user_id="admin-1",
            state=ChatMessageState.HELD.value, delivered_at=None, deleted=False,
        )
        svc._chat_message_repo.get_model = AsyncMock(return_value=held)
        svc._conversations._conversation_repo.get_model = AsyncMock(
            return_value=_conversation(ConversationChannel.WHATSAPP, "+2348012345678")
        )

        await svc.approve("msg-1", "admin-2")

        sender.deliver.assert_awaited_once()

    async def test_a_failing_adapter_never_fails_the_console_write(self, monkeypatch):
        # The agent has already been told their message sent, and the thread is our own
        # record of what was said. Raising here would discard both.
        sender = self._console_sender(monkeypatch)
        sender.deliver = AsyncMock(side_effect=RuntimeError("meta down"))
        svc = _service()
        convo = _conversation(ConversationChannel.WHATSAPP, "+2348012345678")

        msg = await svc.send(convo, "admin-1", SenderKind.ADMIN, "On it — checking now.")

        assert msg.state == ChatMessageState.DELIVERED.value


class TestMediaLabelling:
    """§26.6.3/WA-06 — chat media is flagged unofficial and never becomes evidence."""

    async def test_an_image_is_flagged_unofficial_in_the_console(self):
        from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
            InboundKind,
        )

        svc = _service()
        convo = _conversation(ConversationChannel.WHATSAPP, "+2348012345678")
        msg = await svc.send(
            convo, None, SenderKind.CUSTOMER, "[sent an image]",
            source=MessageSource.WHATSAPP, media_kind=InboundKind.IMAGE,
        )
        svc._users.get_model = AsyncMock(return_value=None)

        dto = await svc._to_dto(msg, None, ConversationChannel.WHATSAPP.value)

        assert dto.media_kind == InboundKind.IMAGE
        # Derived from `media_kind`, never stored: the evidence rule (§26.1.6) says chat
        # media is never canonical, so a persisted flag could only ever drift from it.
        assert dto.unofficial_media is True

    async def test_ordinary_text_carries_no_media_flag(self):
        svc = _service()
        convo = _conversation(ConversationChannel.WHATSAPP, "+2348012345678")
        msg = await svc.send(
            convo, None, SenderKind.CUSTOMER, "How much for a Lagos land check?",
            source=MessageSource.WHATSAPP,
        )
        svc._users.get_model = AsyncMock(return_value=None)

        dto = await svc._to_dto(msg, None, ConversationChannel.WHATSAPP.value)

        assert dto.media_kind is None
        assert dto.unofficial_media is False

    async def test_a_queued_reply_is_marked_pending_only_on_a_channel_thread(self):
        svc = _service()
        svc._users.get_model = AsyncMock(return_value=None)
        queued = SimpleNamespace(
            id="msg-1", conversation_id="conv-1", sender_user_id="admin-1",
            sender_kind=SenderKind.ADMIN.value, source=MessageSource.WEB.value,
            body="Sorry for the delay.", task_id=None,
            state=ChatMessageState.DELIVERED.value,
            message_kind=MessageKind.CHAT.value, clarification_status=None,
            media_kind=None, delivered_at=Utils.datetime_now(),
            channel_delivered_at=None, date_created=Utils.datetime_now(),
        )

        on_whatsapp = await svc._to_dto(queued, None, ConversationChannel.WHATSAPP.value)
        on_web = await svc._to_dto(queued, None, ConversationChannel.WEB.value)

        assert on_whatsapp.pending_channel_delivery is True
        # A web thread has no outbound transport, so nothing on it is ever "waiting to
        # deliver" — it is simply read in the portal.
        assert on_web.pending_channel_delivery is False
