"""A message's bookkeeping row is visible to the rest of its own transaction at once.

`MessageService` is INDEPENDENT, and an independent write nested inside another one joins that
session rather than opening a third. So a send made inside an independent transaction (a payout
settled in `PayoutDisbursementService._settle`, which then announces PAYOUT_PAID) creates its row
in the caller's session, and every later step — `update_message_sent`, a retry, a failure —
first checks the row exists. Sessions run with autoflush off, so an unflushed row is invisible to
that check: the email was delivered, the send was then reported as failed, and the row was
committed PENDING forever. `create_from_upsert` flushes the row as it creates it.
"""
from unittest.mock import AsyncMock

from main.app.domain.message.models import UpsertMessageDto
from main.app.domain.message.repo import MessageRepo
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.messaging.models import EmailPayload, MessageChannel, MessageRecipient
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)


def _dto() -> UpsertMessageDto:
    return UpsertMessageDto(
        channel=MessageChannel.EMAIL,
        to=MessageRecipient(recipient="user@example.com"),
        payload=EmailPayload(subject="Paid", html="<p>Your payout was paid.</p>"),
        extras={},
    )


async def test_the_new_row_is_flushed_so_the_same_transaction_can_find_it():
    session = db_session_ctx.get()
    order = []
    session.add = lambda row: order.append("add")
    session.flush = AsyncMock(side_effect=lambda *a, **k: order.append("flush"))

    row = await MessageRepo(db=None).create_from_upsert(_dto())

    assert order == ["add", "flush"]
    assert row.status == "pending"
