"""Queued delivery — a message written now and sent by the drain (`delivery=QUEUED`).

A notification rule can ask for its email/SMS to be queued rather than sent in the request
(a broadcast to thousands of users). `enqueue_bulk` renders each message exactly as a send
would and persists it as a PENDING `messages` row with `next_retry_at` = now, which is what
makes it due for `drain_due_messages`. Nothing is handed to a provider.

The row is written in the **caller's** transaction, never an independent one. A queued row is
an intention, not a record of something that already happened: if the caller's work rolls
back (a broadcast page that failed), its queued emails must roll back with it, or the page's
retry would queue them a second time.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.message.service import MessageQueueService
from main.appodus_utils.integrations.messaging.channel_sender import MessageDispatcher
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.service import MessagingService, dispatch_delivered
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)


def _email_request(user_id: str = "u-1") -> MessageRequest:
    return MessageRequest(
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient=f"{user_id}@example.com", fullname="Ada QA"),
        payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>"),
        extras={"user_id": user_id},
    )


def _service():
    svc = object.__new__(MessagingService)
    svc.router = AsyncMock()
    svc.message_queue = MagicMock()
    svc.message_queue.enqueue = AsyncMock()
    return svc


class TestEnqueueBulk:
    async def test_each_message_is_stored_due_now_and_never_sent(self):
        svc = _service()
        before = datetime.now(timezone.utc)

        result = await svc.enqueue_bulk([_email_request("u-1"), _email_request("u-2")])

        svc.router.send_message.assert_not_called()
        stored = [c.args[0] for c in svc.message_queue.enqueue.await_args_list]
        assert [m.to.recipient for m in stored] == ["u-1@example.com", "u-2@example.com"]
        for message in stored:
            assert message.status == MessageStatus.PENDING
            assert before - timedelta(seconds=1) <= message.next_retry_at <= datetime.now(timezone.utc)
        assert result.total == 2 and len(result.successes) == 2

    async def test_a_message_that_cannot_be_stored_fails_the_enqueue(self):
        """Queued delivery has no other copy: a row that was not written is a message lost,
        so the failure reaches the caller (and rolls its work back) instead of vanishing."""
        svc = _service()
        svc.message_queue.enqueue = AsyncMock(side_effect=RuntimeError("db down"))

        with pytest.raises(RuntimeError):
            await svc.enqueue_bulk([_email_request()])

    async def test_queued_counts_as_accepted_for_the_caller(self):
        svc = _service()
        assert dispatch_delivered(await svc.enqueue_bulk([_email_request()]))


class TestMessageQueueService:
    async def test_it_writes_in_the_callers_transaction(self, independent_sessions):
        queue = object.__new__(MessageQueueService)
        queue._message_repo = MagicMock()
        queue._message_repo.create_from_upsert = AsyncMock()
        message = MagicMock()

        await queue.enqueue(message)

        queue._message_repo.create_from_upsert.assert_awaited_once_with(message)
        assert independent_sessions == []


class TestDispatcherRoutesQueuedRequests:
    def _dispatcher(self):
        dispatcher = object.__new__(MessageDispatcher)
        dispatcher.messaging_service = MagicMock()
        dispatcher.messaging_service.send_bulk = AsyncMock(return_value="sent")
        dispatcher.messaging_service.enqueue_bulk = AsyncMock(return_value="queued")
        dispatcher._build_requests_for_channels = AsyncMock(return_value=[_email_request()])
        return dispatcher

    async def test_an_immediate_request_is_sent(self):
        dispatcher = self._dispatcher()
        assert await dispatcher.dispatch_bulk([MagicMock()]) == "sent"
        dispatcher.messaging_service.enqueue_bulk.assert_not_called()

    async def test_a_queued_request_is_only_stored(self):
        dispatcher = self._dispatcher()
        assert await dispatcher.dispatch_bulk([MagicMock()], queued=True) == "queued"
        dispatcher.messaging_service.send_bulk.assert_not_called()
