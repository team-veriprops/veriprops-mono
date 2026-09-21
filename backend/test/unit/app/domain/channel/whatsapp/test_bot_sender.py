"""WhatsAppBotSender — a bot reply goes to the phone and into the console thread (§26.6, D92).

The console copy is the one an agent reads, so it is also where Meta's receipts for the
reply have to land: the mirrored message keeps the wamid of what actually went out.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.bot.sender import WhatsAppBotSender
from main.app.domain.communication.chat_message.models import ChannelDeliveryStatus, SenderKind
from main.app.domain.communication.chat_message.repo import ChatMessageRepo
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
    from main.app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ENABLE_OUT_MESSAGING", True)


def _sender(send_message):
    mirrored = SimpleNamespace(
        id="msg-1", channel_delivered_at=None, external_message_id=None,
        channel_status=None, channel_status_at=None,
    )
    svc = object.__new__(WhatsAppBotSender)
    svc._messaging_service = MagicMock(send_message=send_message)
    svc._chat_message_service = MagicMock(send=AsyncMock(return_value=mirrored))
    svc._chat_message_repo = MagicMock(_session=MagicMock())
    svc._chat_message_repo.mark_channel_sent = (
        lambda message, wamid, at: ChatMessageRepo.mark_channel_sent(svc._chat_message_repo, message, wamid, at)
    )
    return svc, mirrored


async def test_the_console_copy_keeps_the_wamid_of_what_went_out():
    svc, mirrored = _sender(AsyncMock(return_value=SimpleNamespace(provider_id="wamid.BOT1")))

    await svc.reply(SimpleNamespace(id="conv-1"), PHONE, "Here's what it costs.")

    assert svc._chat_message_service.send.await_args.args[2] == SenderKind.SYSTEM
    assert mirrored.external_message_id == "wamid.BOT1"
    assert mirrored.channel_status == ChannelDeliveryStatus.SENT.value
    assert mirrored.channel_delivered_at is not None


async def test_a_failed_send_leaves_the_console_copy_unstamped():
    svc, mirrored = _sender(AsyncMock(side_effect=RuntimeError("meta down")))

    await svc.reply(SimpleNamespace(id="conv-1"), PHONE, "Here's what it costs.")

    assert mirrored.channel_status is None
    assert mirrored.external_message_id is None
